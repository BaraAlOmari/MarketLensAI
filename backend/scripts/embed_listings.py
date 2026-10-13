"""Embed listings that have no embedding (or one from another model), then build the HNSW index.

Resumable and safe to re-run: with nothing pending it makes no API calls. On the free tier
every listing counts as one request, so a run stops at the daily budget and the next run
(after midnight Pacific) carries on. Each run is appended to docs/logs/embedding-runs.jsonl.

Usage (from backend/):
    .venv/Scripts/python scripts/embed_listings.py --dry-run    # pending rows, estimate only
    .venv/Scripts/python scripts/embed_listings.py              # embed up to today's budget
    .venv/Scripts/python scripts/embed_listings.py --max-items 200
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import REPO_DIR, get_settings  # noqa: E402
from app.ingestion.embed_job import JobReport, PgEmbeddingStore, run_embedding_job  # noqa: E402
from app.providers.embeddings import estimate_tokens, get_embedding_provider  # noqa: E402

RUN_LOG = REPO_DIR / "docs" / "logs" / "embedding-runs.jsonl"
DATASET = REPO_DIR / "data" / "listings.jsonl"
QUOTA_TZ = ZoneInfo("America/Los_Angeles")  # Gemini RPD resets at midnight Pacific


def quota_day(ts: datetime) -> str:
    return ts.astimezone(QUOTA_TZ).date().isoformat()


def used_today(now: datetime) -> int:
    """Requests this machine already spent today, from the run log (one per text)."""
    if not RUN_LOG.exists():
        return 0
    today = quota_day(now)
    used = 0
    for line in RUN_LOG.read_text(encoding="utf-8").splitlines():
        run = json.loads(line)
        if quota_day(datetime.fromisoformat(run["started_at"])) == today:
            used += run["requests"]
    return used


def gemini_written_ids(path: Path) -> set[str]:
    """Synthetic listings whose text Gemini already rewrote: embed those first, since the
    template-text rows will change (and need re-embedding) after the next rewrite."""
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("meta", {}).get("writer") == "gemini":
            ids.add(record["external_id"])
    return ids


async def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    if settings.database_url is None:
        print("FAIL: DATABASE_URL is not set")
        return 1
    model, dim = settings.embedding_model, settings.embedding_dimension
    now = datetime.now(UTC)

    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), statement_cache_size=0, timeout=15
    )
    try:
        store = PgEmbeddingStore(conn)
        column_dim = await store.column_dimension()
        if column_dim != dim:
            print(f"FAIL: listings.embedding is vector({column_dim}) but EMBEDDING_DIMENSION={dim}")
            return 1
        pending = await store.count_pending(model)
        spent = used_today(now)
        budget = settings.embedding_rpd_limit - settings.embedding_query_reserve - spent
        max_items = args.max_items if args.max_items is not None else max(budget, 0)
        print(
            f"model={model} dim={dim} pending={pending} "
            f"budget today={max(budget, 0)} (RPD {settings.embedding_rpd_limit}, "
            f"reserve {settings.embedding_query_reserve}, already used {spent}) "
            f"-> this run embeds up to {min(pending, max_items)}"
        )

        provider = get_embedding_provider(settings)
        if args.dry_run:
            rows = await store.fetch_pending(model, pending)
            tokens = sum(estimate_tokens(provider.document_input(r.search_text, r.title))
                         for r in rows)  # fmt: skip
            minutes = max(
                len(rows) / (settings.embedding_rpm_limit * 0.9),
                tokens / (settings.embedding_tpm_limit * 0.9),
            )
            cost = tokens / 1e6 * float(settings.embedding_price_per_mtok_usd)
            print(
                f"DRY RUN: {len(rows)} rows, ~{tokens:,} tokens, ~{minutes:.0f} min of quota, "
                f"~{-(-len(rows) // max(budget, 1))} day(s) at today's budget; "
                f"paid-tier cost would be ~${cost:.3f}"
            )
            return 0

        report = JobReport(model=model, dimension=dim)
        prefer = gemini_written_ids(DATASET) if args.prefer_final_text else set()
        try:
            if pending:
                await run_embedding_job(
                    store,
                    provider,
                    max_items=max_items,
                    batch_size=settings.embedding_batch_size,
                    rpm_limit=settings.embedding_rpm_limit,
                    tpm_limit=settings.embedding_tpm_limit,
                    prefer=prefer,
                    report=report,
                )
            else:
                report.stopped = "done"
        finally:
            remaining = await store.count_pending(model)
            if report.api_calls:
                log_run(report, now, remaining, settings.embedding_price_per_mtok_usd)

        index_note = ""
        if remaining == 0 and not args.no_index:
            created = await store.ensure_hnsw_index()
            await conn.execute("analyze listings")
            index_note = "; HNSW index created" if created else "; HNSW index already present"
    finally:
        await conn.close()

    cost = report.cost_usd(float(settings.embedding_price_per_mtok_usd))
    print(
        f"{'OK' if report.stopped == 'done' else 'STOPPED'} ({report.stopped}): "
        f"embedded {report.embedded} in {report.api_calls} calls, {report.duration_s}s, "
        f"~{report.estimated_tokens:,} tokens (paid-tier ~${cost:.4f}, free tier $0); "
        f"{remaining} still pending{index_note}"
    )
    if report.skipped_changed:
        print(f"note: {report.skipped_changed} rows changed text mid-run and stay pending")
    return 0 if report.stopped in ("done", "budget", "daily-quota") else 1


def log_run(report: JobReport, started: datetime, remaining: int, price) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "started_at": started.isoformat(timespec="seconds"),
        "model": report.model,
        "dimension": report.dimension,
        "pending_before": report.pending_before,
        "embedded": report.embedded,
        "skipped_changed": report.skipped_changed,
        # Free tier counts each text as a request; the job sends one text per row.
        "requests": report.embedded + report.skipped_changed,
        "api_calls": report.api_calls,
        "estimated_tokens": report.estimated_tokens,
        "paid_tier_cost_usd": round(report.cost_usd(float(price)), 5),
        "duration_s": report.duration_s,
        "stopped": report.stopped,
        "remaining": remaining,
    }
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="count and estimate only")
    parser.add_argument("--max-items", type=int, help="override today's request budget")
    parser.add_argument("--no-index", action="store_true", help="skip HNSW index creation")
    parser.add_argument(
        "--no-prefer-final-text",
        dest="prefer_final_text",
        action="store_false",
        help="do not embed Gemini-written synthetic listings first",
    )
    sys.exit(asyncio.run(main(parser.parse_args())))
