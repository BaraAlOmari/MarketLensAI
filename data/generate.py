"""MarketLens synthetic dataset generator.

Run from backend/ with the backend venv:

    .venv/Scripts/python ../data/generate.py build         # facts + template text -> listings.jsonl
    .venv/Scripts/python ../data/generate.py rewrite -n 5  # 5 Gemini batches, then rebuild
    .venv/Scripts/python ../data/generate.py status        # Gemini vs template text counts

Options (all commands): --locale qa|us, --seed N, --currency-mix QAR:0.88,USD:0.12, --out PATH.

Text priority per listing: cached Gemini text (if its facts fingerprint still matches),
otherwise the offline template text. Gemini results are cached under data/cache/, so
quota spent is never lost and reruns are free.
"""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(DATA_DIR), str(DATA_DIR.parent / "backend")]

from app.config import get_settings  # noqa: E402
from app.models.listing import NormalizedListing  # noqa: E402
from app.providers.gemini import GeminiJsonClient  # noqa: E402
from app.providers.retry import QuotaExhaustedError  # noqa: E402
from generator.facts import ListingFacts, generate_facts  # noqa: E402
from generator.gemini_writer import GeminiWriter  # noqa: E402
from generator.locales import LOCALES, Locale  # noqa: E402
from generator.template_writer import TemplateWriter  # noqa: E402
from generator.writers import ListingText, facts_fingerprint  # noqa: E402

GENERATOR_VERSION = "1"
MAX_REJECTIONS = 2  # stop asking Gemini for an item it failed on this many times


# ------------------------------------------------------------------ helpers


def parse_mix(text: str | None) -> dict[str, float] | None:
    if not text:
        return None
    mix = {}
    for part in text.split(","):
        code, weight = part.split(":")
        mix[code.strip().upper()] = float(weight)
    return mix


def make_locale(args) -> Locale:
    locale = LOCALES[args.locale]
    mix = parse_mix(args.currency_mix)
    return replace(locale, currency_mix=mix) if mix else locale


def cache_dir(args) -> Path:
    path = DATA_DIR / "cache" / f"{args.locale}-s{args.seed}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_gemini_cache(args) -> dict[str, dict]:
    """Latest accepted Gemini text per external_id."""
    return {row["external_id"]: row for row in read_jsonl(cache_dir(args) / "gemini_texts.jsonl")}


def rejection_counts(args) -> Counter:
    return Counter(r["external_id"] for r in read_jsonl(cache_dir(args) / "gemini_rejects.jsonl"))


def cached_text(f: ListingFacts, cache: dict[str, dict]) -> ListingText | None:
    row = cache.get(f.external_id)
    if row and row["fingerprint"] == facts_fingerprint(f):
        return ListingText(row["title"], row["description"], "gemini")
    return None


def to_record(f: ListingFacts, text: ListingText, args) -> dict:
    record = {
        "source": "synthetic",
        "external_id": f.external_id,
        "title": text.title,
        "description": text.description,
        "category": f.category,
        "brand": f.brand,
        "model": f.model,
        "price": str(f.price),
        "currency": f.currency,
        "condition": f.condition,
        "listing_type": f.listing_type,
        "price_period": f.price_period,
        "attributes": f.attributes,
        "location": f.location,
        "seller_name": f.seller_name,
        "image_url": None,
        "language": f.language,
        "created_at": f.created_at.isoformat(),
    }
    NormalizedListing.model_validate(record)  # fail fast on anything the loader would reject
    record["meta"] = {  # ground truth for the eval set; stripped by the loader
        "writer": text.writer,
        "item_label": f.item_label,
        "price_qar": str(f.price_qar),
        "seller_kind": f.seller_kind,
        "styles": f.styles,
        "omit": f.omit,
        "tags": f.tags,
        "near_duplicate_of": f.near_duplicate_of,
        "locale": args.locale,
        "seed": args.seed,
        "generator_version": GENERATOR_VERSION,
    }
    return record


def default_out(args) -> Path:
    if args.out:
        return Path(args.out)
    if args.locale == "qa" and args.seed == 42 and not args.currency_mix:
        return DATA_DIR / "listings.jsonl"
    return DATA_DIR / f"listings-{args.locale}-s{args.seed}.jsonl"


# ------------------------------------------------------------------ commands


def build(args) -> int:
    facts = generate_facts(make_locale(args), seed=args.seed)
    cache = load_gemini_cache(args)
    template = TemplateWriter()
    records = []
    writers = Counter()
    for f in facts:
        text = cached_text(f, cache) or template.write_one(f)
        writers[text.writer] += 1
        records.append(to_record(f, text, args))
    out = default_out(args)
    tmp = out.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(out)
    print(f"OK: wrote {len(records)} listings to {out.relative_to(DATA_DIR.parent)} "
          f"(text: {dict(writers)})")  # fmt: skip
    return 0


async def rewrite(args) -> int:
    settings = get_settings()
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        print("FAIL: GEMINI_API_KEY is not set in backend/.env")
        return 1
    model = args.model or settings.generator_model or settings.llm_model
    batch_size = args.batch_size or settings.generator_batch_size
    interval = 60.0 / settings.generator_rpm
    writer = GeminiWriter(GeminiJsonClient(settings.gemini_api_key.get_secret_value(), model))

    facts = generate_facts(make_locale(args), seed=args.seed)
    cache, rejects = load_gemini_cache(args), rejection_counts(args)
    pending = [
        f for f in facts if not cached_text(f, cache) and rejects[f.external_id] < MAX_REJECTIONS
    ]
    print(f"model={model} batch_size={batch_size} pending={len(pending)} requests<={args.n}")
    cdir = cache_dir(args)
    last_start = 0.0
    for i in range(args.n):
        batch = pending[i * batch_size : (i + 1) * batch_size]
        if not batch:
            print("OK: nothing left to rewrite")
            break
        wait = interval - (time.monotonic() - last_start)
        if last_start and wait > 0:
            await asyncio.sleep(wait)
        last_start = time.monotonic()
        try:
            texts = await writer.write(batch)
        except QuotaExhaustedError:
            print("STOP: daily quota exhausted; progress is saved, rerun after the reset "
                  "(midnight Pacific time)")  # fmt: skip
            break
        latency = time.monotonic() - last_start
        report = writer.last_report
        now = datetime.now(UTC).isoformat()
        by_id = {f.external_id: f for f in batch}
        append_jsonl(cdir / "gemini_texts.jsonl", [
            {"external_id": eid, "fingerprint": facts_fingerprint(by_id[eid]), "title": t.title,
             "description": t.description, "model": model, "ts": now}
            for eid, t in texts.items()
        ])  # fmt: skip
        append_jsonl(cdir / "gemini_rejects.jsonl",
                     [{"external_id": eid, "ts": now} for eid in report.rejected_ids])  # fmt: skip
        u = report.usage
        append_jsonl(cdir / "usage.jsonl", [{
            "ts": now, "model": model, "requested": report.requested, "accepted": report.accepted,
            "rejected": dict(report.rejected), "latency_s": round(latency, 1),
            "input_tokens": u.input_tokens if u else 0,
            "output_tokens": u.output_tokens if u else 0,
            "thought_tokens": u.thought_tokens if u else 0,
        }])  # fmt: skip
        tokens = f"{u.input_tokens}/{u.output_tokens}/{u.thought_tokens}" if u else "?"
        print(f"batch {i + 1}: accepted {report.accepted}/{report.requested} "
              f"rejected={dict(+report.rejected)} {latency:.0f}s "
              f"tokens in/out/thought={tokens}")  # fmt: skip
    return build(args)


def status(args) -> int:
    facts = generate_facts(make_locale(args), seed=args.seed)
    cache = load_gemini_cache(args)
    done = sum(1 for f in facts if cached_text(f, cache))
    usage = read_jsonl(cache_dir(args) / "usage.jsonl")
    tokens = Counter()
    for row in usage:
        for k in ("input_tokens", "output_tokens", "thought_tokens", "requested", "accepted"):
            tokens[k] += row.get(k, 0)
    print(f"listings: {len(facts)}  gemini text: {done}  template text: {len(facts) - done}")
    print(f"gemini requests so far: {len(usage)}  {dict(tokens)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("build", "rewrite", "status"))
    parser.add_argument("--locale", default="qa", choices=sorted(LOCALES))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--currency-mix", help="e.g. QAR:0.88,USD:0.12")
    parser.add_argument("--out", help="output JSONL path")
    parser.add_argument("-n", type=int, default=1, help="rewrite: max Gemini requests")
    parser.add_argument("--batch-size", type=int, help="rewrite: listings per request")
    parser.add_argument("--model", help="rewrite: override GENERATOR_MODEL / LLM_MODEL")
    args = parser.parse_args()
    if args.command == "build":
        return build(args)
    if args.command == "status":
        return status(args)
    return asyncio.run(rewrite(args))


if __name__ == "__main__":
    sys.exit(main())
