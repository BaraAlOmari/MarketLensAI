"""Stage 7 acceptance: run every eval query through POST /api/chat and check grounding.

For each reply:
1. every cited listing id is one of the listings sent in the `listings` event;
2. the reply text contains no price, link, e-mail or phone number;
3. every card's title, price and currency equal the database row for that id
   (re-read straight from Postgres, independent of the app).
Any violation is listed and the script exits with code 1.

Usage (from backend/):
    .venv/Scripts/python ../eval/grounding_check.py
    .venv/Scripts/python ../eval/grounding_check.py --concurrency 2 --llm-timeout 60
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import asyncpg
import httpx

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(EVAL_DIR))
from app.answers.grounding import has_link, has_price  # noqa: E402
from app.config import get_settings  # noqa: E402
from ground_truth import load_queries  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields.get("event", ""), json.loads(fields.get("data", "{}"))))
    return events


async def run(args) -> dict:
    from app.main import create_app

    settings = get_settings()
    if args.llm_timeout:
        settings = settings.model_copy(
            update={"extraction_timeout_s": args.llm_timeout, "rerank_timeout_s": args.llm_timeout,
                    "extraction_max_attempts": 3, "rerank_max_attempts": 3}
        )  # fmt: skip
    app = create_app(settings)
    queries = load_queries()
    gate = asyncio.Semaphore(args.concurrency)
    db = await asyncpg.connect(settings.database_url.get_secret_value(), statement_cache_size=0)
    # Each query is its own one-turn conversation (sessions are real since Stage 8).
    run = uuid.uuid4().hex[:8]
    db_lock = asyncio.Lock()

    async def one(client, q) -> dict:
        async with gate:
            t0 = time.perf_counter()
            session_id = f"grounding-{run}-{q['id']}"
            resp = await client.post(
                "/api/chat", json={"session_id": session_id, "message": q["query"]}
            )
            wall = (time.perf_counter() - t0) * 1000
        events = parse_sse(resp.text)
        names = [n for n, _ in events]
        cards = next((d["listings"] for n, d in events if n == "listings"), [])
        done = events[-1][1] if names and names[-1] == "done" else {}
        text = "".join(d["text"] for n, d in events if n == "token")
        problems = []
        if names[:2] != ["filters", "listings"] or names[-1:] != ["done"]:
            problems.append(f"event order {names}")
        card_ids = [c["id"] for c in cards]
        for cid in done.get("cited_ids", []):
            if cid not in card_ids:
                problems.append(f"cited id {cid} was not sent")
        if has_price(text):
            problems.append("price in reply text")
        if has_link(text):
            problems.append("link or contact in reply text")
        async with db_lock:  # one connection, shared by concurrent queries
            fetched = await db.fetch(
                "select id, title, price, currency from listings where id = any($1::bigint[])",
                card_ids,
            )
        rows = {r["id"]: r for r in fetched}
        for c in cards:
            r = rows.get(c["id"])
            if r is None:
                problems.append(f"card {c['id']} is not in the database")
            elif (c["title"], Decimal(c["price"]), c["currency"]) != (
                r["title"], r["price"], r["currency"].strip()
            ):  # fmt: skip
                problems.append(f"card {c['id']} differs from the database row")
        answer = done.get("answer", {})
        return {
            "id": q["id"], "query": q["query"], "lang": q["lang"], "cards": len(cards),
            "cited": done.get("cited_ids", []), "reply": text, "problems": problems,
            "grounding": done.get("grounding"), "answer": answer,
            "timings_ms": done.get("timings_ms", {}), "wall_ms": round(wall, 1),
        }  # fmt: skip

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://g", timeout=600
            ) as c:
                rows = await asyncio.gather(*(one(c, q) for q in queries))
    finally:
        await db.close()

    price_in = float(settings.extraction_input_price_per_mtok_usd)
    price_out = float(settings.extraction_output_price_per_mtok_usd)
    llm = [r["answer"] for r in rows if r["answer"].get("source") == "llm"]
    fresh = [a for a in llm if not a.get("cached")]
    grounding = [r["grounding"] or {} for r in rows]

    def cost(a: dict) -> float:
        out_tokens = a["output_tokens"] + a["thought_tokens"]
        return a["input_tokens"] / 1e6 * price_in + out_tokens / 1e6 * price_out

    def mean(values, default=None):
        values = list(values)
        return statistics.fmean(values) if values else default

    return {
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "queries": len(rows),
        "violations": sum(len(r["problems"]) for r in rows),
        "sources": {
            s: sum(1 for r in rows if r["answer"].get("source") == s)
            for s in ("llm", "template", "no-match template")
        },
        "answer_errors": sum(1 for r in rows if r["answer"].get("error")),
        "dropped_ids": sum(len(g.get("dropped_ids", [])) for g in grounding),
        "removed_sentences": sum(g.get("removed_sentences", 0) for g in grounding),
        "templates_after_removal": sum(1 for g in grounding if g.get("used_template")),
        "answer_latency_mean_ms": mean(a["latency_ms"] for a in fresh),
        "total_ms_mean": mean((r["timings_ms"].get("total", 0) for r in rows), 0.0),
        "answer_cost_mean_usd": mean((cost(a) for a in llm), 0.0),
        "answer_input_tokens_mean": mean((a["input_tokens"] for a in llm), 0),
        "rows": rows,
    }


def markdown(s: dict) -> str:
    lines = [
        "# Stage 7 grounding check",
        "",
        f"{s['date']} · {s['queries']} eval queries through `POST /api/chat`",
        "",
        "| Violations | Answers (LLM / template / no-match) | Hallucinated ids dropped | "
        "Sentences removed (price/link) | Answer latency (uncached) | Answer cost (paid) |",
        "|---|---|---|---|---|---|",
        f"| **{s['violations']}** | {s['sources']['llm']} / {s['sources']['template']} / "
        f"{s['sources']['no-match template']} | {s['dropped_ids']} | {s['removed_sentences']} | "
        + (f"{s['answer_latency_mean_ms']:.0f} ms" if s["answer_latency_mean_ms"] else "cached")
        + f" | ${s['answer_cost_mean_usd']:.6f} |",
        "",
        "Checks per reply: cited ids ⊆ cards sent; no price, link or phone number in the text; "
        "every card's title, price and currency equal the database row.",
        "",
        "| id | lang | cards | cited | problems | reply |",
        "|---|---|---|---|---|---|",
    ]
    for r in s["rows"]:
        reply = r["reply"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {r['id']} | {r['lang']} | {r['cards']} | {len(r['cited'])} | "
                     f"{'; '.join(r['problems']) or '-'} | {reply} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--llm-timeout", type=float, help="seconds per LLM call")
    args = parser.parse_args()
    s = asyncio.run(run(args))
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = f"{s['date'][:10]}-stage-7-grounding"
    (RESULTS_DIR / f"{stem}.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )
    (RESULTS_DIR / f"{stem}.md").write_text(markdown(s), encoding="utf-8")
    print(
        f"{'PASS' if s['violations'] == 0 else 'FAIL'}: {s['violations']} violations in "
        f"{s['queries']} replies; sources {s['sources']}; dropped ids {s['dropped_ids']}; "
        f"removed sentences {s['removed_sentences']}; answer errors {s['answer_errors']} "
        f"-> {RESULTS_DIR / stem}.md"
    )
    for r in s["rows"]:
        if r["problems"]:
            print(f"  {r['id']}: {r['problems']}")
    return 0 if s["violations"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
