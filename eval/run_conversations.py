"""Run the multi-turn eval (eval/conversations.json) through POST /api/chat.

Each conversation gets a fresh session id; its turns are sent in order. Scored turns are
checked against ground truth from the generator's facts (eval/conversations.py).
Pass rule, fixed before the first run: every scored turn has 0 wrong results in its top 10
and Recall@10 >= 0.8.

Usage (from backend/):
    .venv/Scripts/python ../eval/run_conversations.py
    .venv/Scripts/python ../eval/run_conversations.py --concurrency 2 --llm-timeout 60
"""

import argparse
import asyncio
import json
import statistics
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(EVAL_DIR))
from conversations import (  # noqa: E402
    comparable_price,
    conversation_truth,
    load_conversations,
    turn_violations,
)

from app.config import get_settings  # noqa: E402
from ground_truth import load_facts  # noqa: E402
from run import recall_at_k, reciprocal_rank  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"
RESULTS_MD = REPO_DIR / "docs" / "results.md"
K = 10
MIN_RECALL = 0.8


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
    facts = load_facts()
    conversations = load_conversations()
    gate = asyncio.Semaphore(args.concurrency)
    run_id = uuid.uuid4().hex[:8]

    async def one(client, conv) -> dict:
        truth = conversation_truth(conv, facts)
        medians = {
            n: statistics.median(comparable_price(facts[x]) for x in ids)
            for n, ids in truth.items()
            if ids
        }
        session_id = f"conv-{run_id}-{conv['id']}"
        turns = []
        async with gate:
            for number, turn in enumerate(conv["turns"], 1):
                resp = await client.post(
                    "/api/chat", json={"session_id": session_id, "message": turn["message"]}
                )
                events = parse_sse(resp.text)
                filters_event = next((d for n, d in events if n == "filters"), {})
                cards = next((d["listings"] for n, d in events if n == "listings"), [])
                done = events[-1][1] if events and events[-1][0] == "done" else {}
                returned = [c["external_id"] for c in cards]
                row = {
                    "turn": number,
                    "message": turn["message"],
                    "filters": filters_event.get("filters"),
                    "notes": filters_event.get("notes"),
                    "returned": returned,
                    "reply": "".join(d["text"] for n, d in events if n == "token"),
                    "total_ms": done.get("timings_ms", {}).get("total"),
                }
                if number in truth:
                    relevant = set(truth[number])
                    wrong = {
                        x: turn_violations(facts[x], turn, medians)
                        for x in returned[:K]
                        if x not in relevant
                    }
                    row.update(
                        scored=True,
                        relevant_count=len(relevant),
                        hits=sum(1 for x in returned[:K] if x in relevant),
                        recall_at_10=recall_at_k(returned, relevant),
                        rr=reciprocal_rank(returned, relevant),
                        wrong=wrong,
                        passed=not wrong and recall_at_k(returned, relevant) >= MIN_RECALL,
                    )
                turns.append(row)
        scored = [t for t in turns if t.get("scored")]
        return {
            "id": conv["id"],
            "lang": conv["lang"],
            "tags": conv["tags"],
            "turns": turns,
            "passed": all(t["passed"] for t in scored),
        }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://c", timeout=600) as c:
            results = await asyncio.gather(*(one(c, conv) for conv in conversations))

    scored = [t for r in results for t in r["turns"] if t.get("scored")]
    last = [next(t for t in reversed(r["turns"]) if t.get("scored")) for r in results]
    return {
        "label": args.label,
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "conversations": len(results),
        "passed": sum(r["passed"] for r in results),
        "scored_turns": len(scored),
        "turns_passed": sum(t["passed"] for t in scored),
        "recall_at_10": statistics.fmean(t["recall_at_10"] for t in scored),
        "mrr": statistics.fmean(t["rr"] for t in scored),
        "final_recall_at_10": statistics.fmean(t["recall_at_10"] for t in last),
        "wrong_results": sum(len(t["wrong"]) for t in scored),
        "results": results,
    }


def markdown(s: dict) -> str:
    lines = [
        f"# Multi-turn eval: {s['label']}",
        "",
        f"{s['date']} · {s['conversations']} conversations · {s['scored_turns']} scored turns",
        "",
        "| Conversations passed | Scored turns passed | Recall@10 (all scored) | "
        "Recall@10 (final turns) | MRR | Wrong in top 10 |",
        "|---|---|---|---|---|---|",
        f"| **{s['passed']}/{s['conversations']}** | {s['turns_passed']}/{s['scored_turns']} | "
        f"{s['recall_at_10']:.3f} | {s['final_recall_at_10']:.3f} | {s['mrr']:.3f} | "
        f"{s['wrong_results']} |",
        "",
        f"Pass rule: every scored turn has 0 wrong results in its top {K} and "
        f"Recall@{K} >= {MIN_RECALL}.",
        "",
    ]
    for r in s["results"]:
        lines += [
            f"## {r['id']} ({r['lang']}, {', '.join(r['tags'])}): "
            f"{'PASS' if r['passed'] else 'FAIL'}",
            "",
            "| turn | message | scored | relevant | hits@10 | Recall@10 | wrong | filters "
            "| notes |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for t in r["turns"]:
            f = dict(t["filters"] or {})
            f.pop("keywords", None)
            wrong = "; ".join(sorted({v for vs in t.get("wrong", {}).values() for v in vs})) or "-"
            lines.append(
                f"| {t['turn']} | {t['message']} | {'yes' if t.get('scored') else '-'} | "
                f"{t.get('relevant_count', '-')} | {t.get('hits', '-')} | "
                + (f"{t['recall_at_10']:.2f}" if t.get("scored") else "-")
                + f" | {wrong if t.get('scored') else '-'} | "
                f"{json.dumps(f, ensure_ascii=False).replace('|', '/')} | "
                f"{', '.join(t['notes'] or [])} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def record(s: dict, report: Path) -> None:
    row = (
        f"| {s['date'][:10]} | {s['label']} | {s['passed']}/{s['conversations']} | "
        f"{s['turns_passed']}/{s['scored_turns']} | {s['recall_at_10']:.3f} | "
        f"{s['final_recall_at_10']:.3f} | {s['wrong_results']} | "
        f"[report](../eval/results/{report.name}) |"
    )
    text = RESULTS_MD.read_text(encoding="utf-8")
    marker = "<!-- conversations:end -->"
    if marker not in text:
        raise SystemExit(f"FAIL: {RESULTS_MD} has no '{marker}' line")
    RESULTS_MD.write_text(text.replace(marker, row + "\n" + marker), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="dev run")
    parser.add_argument("--record", action="store_true", help="append a row to docs/results.md")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--llm-timeout", type=float, help="seconds per LLM call")
    args = parser.parse_args()
    s = asyncio.run(run(args))
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = f"{s['date'][:10]}-conversations-{args.label.lower().replace(' ', '-')}"
    stem = "".join(ch for ch in stem if ch.isalnum() or ch == "-")
    (RESULTS_DIR / f"{stem}.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )
    report = RESULTS_DIR / f"{stem}.md"
    report.write_text(markdown(s), encoding="utf-8")
    if args.record:
        record(s, report)
    print(
        f"{args.label}: {s['passed']}/{s['conversations']} conversations passed, "
        f"{s['turns_passed']}/{s['scored_turns']} scored turns, Recall@10 "
        f"{s['recall_at_10']:.3f} (final turns {s['final_recall_at_10']:.3f}), "
        f"wrong {s['wrong_results']} -> {report}"
    )
    for r in s["results"]:
        if not r["passed"]:
            for t in r["turns"]:
                if t.get("scored") and not t["passed"]:
                    reasons = sorted({v for vs in t["wrong"].values() for v in vs})
                    print(
                        f"  {r['id']} turn {t['turn']} {t['message']!r}: recall "
                        f"{t['recall_at_10']:.2f}, wrong {reasons}, filters {t['filters']}"
                    )
    return 0 if s["passed"] == s["conversations"] else 1


if __name__ == "__main__":
    sys.exit(main())
