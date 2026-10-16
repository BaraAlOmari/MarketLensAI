"""Run the eval set through POST /api/search and score it (Recall@10, MRR, latency, cost).

By default the FastAPI app runs in-process (same code path as the server); pass --url to hit a
running backend instead. Query embeddings and LLM extractions are cached in Postgres, so after
the first run the numbers reproduce exactly without spending quota.

Usage (from backend/):
    .venv/Scripts/python ../eval/run.py                              # print scores
    .venv/Scripts/python ../eval/run.py --label "Stage 4 filters" --record   # + docs/results.md
    .venv/Scripts/python ../eval/run.py --no-extract --retrieval vector --no-rerank  # Stage 3
    .venv/Scripts/python ../eval/run.py --retrieval vector --no-rerank   # Stage 4
    .venv/Scripts/python ../eval/run.py --no-rerank                  # Stage 5
    .venv/Scripts/python ../eval/run.py --concurrency 4 --extraction-timeout 150   # fill caches
    .venv/Scripts/python ../eval/run.py --url http://localhost:8000
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(EVAL_DIR))
from app.config import get_settings  # noqa: E402
from app.providers.embeddings import estimate_tokens, get_embedding_provider  # noqa: E402
from ground_truth import build, load_facts, load_queries, violations  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"
RESULTS_MD = REPO_DIR / "docs" / "results.md"
K = 10


def recall_at_k(returned: list[str], relevant: set[str], k: int = K) -> float:
    """Share of the reachable relevant listings found in the top k.

    The denominator is min(|relevant|, k): with 40 relevant listings, a perfect top 10
    scores 1.0 rather than 0.25.
    """
    if not relevant:
        return 0.0
    hits = sum(1 for x in returned[:k] if x in relevant)
    return hits / min(len(relevant), k)


def reciprocal_rank(returned: list[str], relevant: set[str], k: int = K) -> float:
    for rank, x in enumerate(returned[:k], 1):
        if x in relevant:
            return 1.0 / rank
    return 0.0


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


@asynccontextmanager
async def search_client(args):
    if args.url:
        async with httpx.AsyncClient(base_url=args.url, timeout=300) as client:
            yield client
        return
    from app.main import create_app

    settings = get_settings()
    # One in-process client sends every query, so the per-IP limit (Stage 10) is off.
    settings = settings.model_copy(update={"rate_limit_enabled": False})
    if args.extraction_timeout:
        settings = settings.model_copy(update={"extraction_timeout_s": args.extraction_timeout})
    if args.hybrid_keywords:
        settings = settings.model_copy(update={"hybrid_keywords": args.hybrid_keywords})
    if args.extraction_attempts:
        settings = settings.model_copy(update={"extraction_max_attempts": args.extraction_attempts})
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://eval", timeout=300) as c:
            yield c


def llm_cost_usd(call: dict | None, settings) -> float:
    """Paid-tier price of one LLM call (extraction or rerank; both use the same model)."""
    if not call or call.get("error"):
        return 0.0
    cost = call["input_tokens"] / 1e6 * float(settings.extraction_input_price_per_mtok_usd)
    out_tokens = call["output_tokens"] + call["thought_tokens"]
    return cost + out_tokens / 1e6 * float(settings.extraction_output_price_per_mtok_usd)


def query_cost_usd(model_input: str, extraction: dict | None, rerank: dict | None, settings):
    """Paid-tier price of one uncached query: embedding + LLM extraction + LLM rerank."""
    cost = estimate_tokens(model_input) / 1e6 * float(settings.embedding_price_per_mtok_usd)
    return cost + llm_cost_usd(extraction, settings) + llm_cost_usd(rerank, settings)


async def run(args) -> dict:
    queries = load_queries()
    facts = load_facts()
    truth = build(queries, facts)
    settings = get_settings()
    provider = get_embedding_provider(settings)  # only for the exact model input (no calls)
    gate = asyncio.Semaphore(args.concurrency)

    async def one(client, q) -> dict:
        async with gate:
            t0 = time.perf_counter()
            resp = await client.post(
                "/api/search",
                json={
                    "query": q["query"],
                    "limit": K,
                    "debug": True,
                    "extract": not args.no_extract,
                    "retrieval": args.retrieval,
                    "rerank": False if args.no_rerank else None,
                },
            )
            wall_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code != 200:
            raise SystemExit(f"FAIL: {q['id']} -> HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        debug = body["debug"]
        extraction = debug.get("extraction")
        returned = [r["external_id"] for r in body["results"]]
        relevant = set(truth[q["id"]])
        wrong = {x: violations(facts[x], q["relevant"]) for x in returned[:K] if x not in relevant}
        return {
            "id": q["id"],
            "query": q["query"],
            "lang": q["lang"],
            "tags": q["tags"],
            "relevant_count": len(relevant),
            "returned": returned,
            "hits": sum(1 for x in returned[:K] if x in relevant),
            "recall_at_10": recall_at_k(returned, relevant),
            "rr": reciprocal_rank(returned, relevant),
            "violations": wrong,
            "filters": body["extracted_filters"],
            "extraction": extraction,
            "rerank": debug.get("rerank"),
            "wall_ms": round(wall_ms, 1),
            "server_ms": debug["timings_ms"],
            "embedding_cached": debug["embedding_cached"],
            "est_cost_usd_uncached": query_cost_usd(
                provider.query_input(q["query"]), extraction, debug.get("rerank"), settings
            ),
        }

    async with search_client(args) as client:
        per_query = await asyncio.gather(*(one(client, q) for q in queries))
    return summarize(list(per_query), args)


def summarize(per_query: list[dict], args) -> dict:
    def mean(key, rows=per_query):
        return statistics.fmean(r[key] for r in rows) if rows else 0.0

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in per_query:
        groups[f"lang:{r['lang']}"].append(r)
        for t in r["tags"]:
            groups[f"tag:{t}"].append(r)

    # Failure categories: why the wrong listings in each top 10 were wrong.
    results_total = sum(min(K, len(r["returned"])) for r in per_query)
    reasons = Counter()
    queries_hit = Counter()
    for r in per_query:
        seen = set()
        for broken in r["violations"].values():
            for v in broken:
                reasons[v] += 1
                seen.add(v)
        queries_hit.update(seen)

    extractions = [r["extraction"] for r in per_query if r["extraction"]]
    uncached_llm = [e["latency_ms"] for e in extractions if not e["cached"] and not e["error"]]
    reranks = [r["rerank"] for r in per_query if r.get("rerank")]
    uncached_rr = [x["latency_ms"] for x in reranks if not x["cached"] and not x["error"]]
    server_total = [r["server_ms"]["total"] for r in per_query]
    return {
        "label": args.label,
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "queries": len(per_query),
        "recall_at_10": mean("recall_at_10"),
        "mrr": mean("rr"),
        "zero_hit_queries": sum(1 for r in per_query if r["hits"] == 0),
        "short_pages": sum(1 for r in per_query if len(r["returned"]) < K),
        "empty_pages": sum(1 for r in per_query if not r["returned"]),
        "extraction": {
            "used": len(extractions),
            "failed": sum(1 for e in extractions if e["error"]),
            "cached": sum(1 for e in extractions if e["cached"]),
            "uncached_latency_mean_ms": statistics.fmean(uncached_llm) if uncached_llm else None,
        },
        "rerank": {
            "used": len(reranks),
            "failed": sum(1 for x in reranks if x["error"]),
            "cached": sum(1 for x in reranks if x["cached"]),
            "uncached_latency_mean_ms": statistics.fmean(uncached_rr) if uncached_rr else None,
            "input_tokens_mean": statistics.fmean(x["input_tokens"] for x in reranks)
            if reranks
            else None,
        },
        "latency_ms": {
            "server_mean": statistics.fmean(server_total),
            "server_p95": p95(server_total),
            "wall_mean": mean("wall_ms"),
            "cached_embeddings": sum(r["embedding_cached"] for r in per_query),
        },
        "est_cost_per_query_usd": mean("est_cost_usd_uncached"),
        "groups": {
            g: {"n": len(rows), "recall_at_10": mean("recall_at_10", rows), "mrr": mean("rr", rows)}
            for g, rows in sorted(groups.items())
        },
        "failures": {
            "wrong_results": sum(len(r["violations"]) for r in per_query),
            "results_total": results_total,
            "by_reason": {
                k: {"results": v, "queries": queries_hit[k]} for k, v in reasons.most_common()
            },
        },
        "per_query": per_query,
    }


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "run"


def wrong_share(s: dict) -> float:
    total = s["failures"]["results_total"]
    return s["failures"]["wrong_results"] / total if total else 0.0


def compact(filters: dict | None) -> str:
    if not filters:
        return "-"
    parts = []
    for key, value in filters.items():
        if key == "attributes":
            parts += [f"{k}:{list(v.values())[0]}" for k, v in value.items()]
        elif isinstance(value, list):
            parts.append(f"{key}={'/'.join(map(str, value))}")
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def rerank_line(rr: dict | None) -> str:
    if not rr or not rr["used"]:
        return " Rerank: off."
    line = f" Rerank: used on {rr['used']}, cached {rr['cached']}, failed {rr['failed']}"
    if rr["uncached_latency_mean_ms"]:
        line += f"; uncached rerank mean {rr['uncached_latency_mean_ms']:.0f} ms"
    return line + f"; mean {rr['input_tokens_mean']:.0f} input tokens."


def markdown(s: dict) -> str:
    lat, ex = s["latency_ms"], s["extraction"]
    lines = [
        f"# Eval run: {s['label']}",
        "",
        f"{s['date']} · {s['queries']} queries · k = {K}",
        "",
        "| Recall@10 | MRR | Wrong in top 10 | Zero-hit | Pages < 10 results | "
        "Server latency mean / p95 | Est. cost/query |",
        "|---|---|---|---|---|---|---|",
        f"| {s['recall_at_10']:.3f} | {s['mrr']:.3f} | {wrong_share(s):.0%} | "
        f"{s['zero_hit_queries']} | {s['short_pages']} ({s['empty_pages']} empty) | "
        f"{lat['server_mean']:.0f} / {lat['server_p95']:.0f} ms | "
        f"${s['est_cost_per_query_usd']:.6f} |",
        "",
        f"Cached query embeddings: {lat['cached_embeddings']}/{s['queries']}. "
        f"LLM extraction: used on {ex['used']}, cached {ex['cached']}, failed {ex['failed']}"
        + (
            f"; uncached extraction mean {ex['uncached_latency_mean_ms']:.0f} ms."
            if ex["uncached_latency_mean_ms"]
            else "."
        )
        + rerank_line(s.get("rerank")),
        "",
        "## By language and tag",
        "",
        "| group | n | Recall@10 | MRR |",
        "|---|---|---|---|",
        *[
            f"| {g} | {v['n']} | {v['recall_at_10']:.3f} | {v['mrr']:.3f} |"
            for g, v in s["groups"].items()
        ],
        "",
        "## Why wrong results were wrong",
        "",
        f"{s['failures']['wrong_results']} of {s['failures']['results_total']} top-{K} "
        "results were not relevant. A result can break several constraints.",
        "",
        "| broken constraint | wrong results | queries affected |",
        "|---|---|---|",
        *[
            f"| {k} | {v['results']} | {v['queries']} |"
            for k, v in s["failures"]["by_reason"].items()
        ],
        "",
        "## Per query",
        "",
        "| id | lang | query | relevant | returned | hits@10 | Recall@10 | RR | "
        "main reasons | filters |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["per_query"]:
        top = Counter(v for vs in r["violations"].values() for v in vs).most_common(3)
        reasons = ", ".join(f"{k} ×{n}" for k, n in top) or "-"
        err = r["extraction"]["error"] if r["extraction"] and r["extraction"]["error"] else None
        filters = f"FAILED: {err}" if err else compact(r["filters"])
        lines.append(
            f"| {r['id']} | {r['lang']} | {r['query']} | {r['relevant_count']} | "
            f"{len(r['returned'])} | {r['hits']} | {r['recall_at_10']:.2f} | {r['rr']:.2f} | "
            f"{reasons} | {filters.replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def record(s: dict, report: Path) -> None:
    lat = s["latency_ms"]
    row = (
        f"| {s['date'][:10]} | {s['label']} | {s['recall_at_10']:.3f} | {s['mrr']:.3f} | "
        f"{wrong_share(s):.0%} | {s['zero_hit_queries']}/{s['queries']} | "
        f"{lat['server_mean']:.0f} / {lat['server_p95']:.0f} | "
        f"${s['est_cost_per_query_usd']:.6f} | [report](../eval/results/{report.name}) |"
    )
    text = RESULTS_MD.read_text(encoding="utf-8")
    marker = "<!-- runs:end -->"
    if marker not in text:
        raise SystemExit(f"FAIL: {RESULTS_MD} has no '{marker}' line")
    RESULTS_MD.write_text(text.replace(marker, row + "\n" + marker), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="running backend, e.g. http://localhost:8000")
    parser.add_argument("--label", default="dev run")
    parser.add_argument("--record", action="store_true", help="append a row to docs/results.md")
    parser.add_argument("--no-extract", action="store_true", help="skip query understanding")
    parser.add_argument("--no-rerank", action="store_true", help="skip reranking (Stage 5)")
    parser.add_argument(
        "--retrieval",
        choices=["hybrid", "vector"],
        help="override RETRIEVAL_MODE (vector = Stage 4)",
    )
    parser.add_argument("--concurrency", type=int, default=1, help="queries in flight")
    parser.add_argument(
        "--extraction-timeout", type=float, help="seconds per LLM call (in-process only)"
    )
    parser.add_argument(
        "--hybrid-keywords", choices=["llm", "query"], help="full-text input (in-process)"
    )
    parser.add_argument(
        "--extraction-attempts", type=int, help="LLM attempts per query (in-process only)"
    )
    args = parser.parse_args()

    summary = asyncio.run(run(args))
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = f"{summary['date'][:10]}-{slug(args.label)}"
    (RESULTS_DIR / f"{stem}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    report = RESULTS_DIR / f"{stem}.md"
    report.write_text(markdown(summary), encoding="utf-8")
    if args.record:
        record(summary, report)

    lat, ex = summary["latency_ms"], summary["extraction"]
    print(
        f"{args.label}: Recall@10 {summary['recall_at_10']:.3f}  MRR {summary['mrr']:.3f}  "
        f"wrong {wrong_share(summary):.0%}  zero-hit {summary['zero_hit_queries']}/"
        f"{summary['queries']}  short pages {summary['short_pages']} "
        f"({summary['empty_pages']} empty)  latency {lat['server_mean']:.0f}/"
        f"{lat['server_p95']:.0f} ms  extraction used {ex['used']} cached {ex['cached']} "
        f"failed {ex['failed']} {rerank_line(summary.get('rerank')).strip()}  -> {report}"
    )
    for reason, v in summary["failures"]["by_reason"].items():
        print(f"  {reason:22} {v['results']:4} wrong results in {v['queries']} queries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
