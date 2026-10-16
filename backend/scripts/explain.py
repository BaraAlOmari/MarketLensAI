"""Explain one search from the logs: what was understood, what was retrieved, and why each
result is on the page (Stage 10).

The backend writes JSON log lines to LOG_FILE (set it in backend/.env). Every request has an
ID, returned in the `x-request-id` response header and shown in the UI on errors.

Usage (from backend/):
    .venv/Scripts/python scripts/explain.py --last
    .venv/Scripts/python scripts/explain.py 3f9c0b2e8d1a4c6f
    .venv/Scripts/python scripts/explain.py --last --log logs/marketlens.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


def load(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a non-JSON line (e.g. uvicorn's own startup output)
    return records


def describe_filters(filters: dict | None) -> str:
    if not filters:
        return "none (searched on meaning and words only)"
    parts = []
    for key, value in filters.items():
        if key == "keywords":
            continue
        if key == "attributes":
            parts += [f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in value.items()]
        elif isinstance(value, list):
            parts.append(f"{key}={' | '.join(map(str, value))}")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def explain(request_id: str, records: list[dict]) -> str:
    steps = [r for r in records if r.get("request_id") == request_id and r.get("event")]
    if not steps:
        return f"No pipeline records for request {request_id}."
    out = [f"Request {request_id}"]
    # In the chat, the model reads the message in the chat step (chat.understand) and the
    # search receives the merged filters, so the search reports source "request".
    edited = any(r["event"] == "chat.turn" and r.get("edited") for r in steps)
    chat_read = any(r["event"] == "chat.understand" for r in steps)
    searches = 0  # a second search in one chat turn is the closest-matches search
    for r in steps:
        event = r["event"]
        if event == "chat.understand":
            cached = " (cached)" if r.get("cached") else ""
            out.append(f'\nMessage: "{r["message"]}"')
            out.append(
                f"0. Read by the language model{cached} as: {describe_filters(r.get('read_as'))}"
            )
            if r.get("guard_notes"):
                out.append(f"   Guards changed: {'; '.join(r['guard_notes'])}")
            if r.get("error"):
                out.append(f"   Reading failed, previous filters kept: {r['error']}")
            if r.get("previous"):
                notes = ", ".join(r["merge_notes"]) or "no change"
                out.append(f"   Merged with the conversation ({notes})")
        elif event == "search.understand":
            request_source = (
                "the person's edited tokens" if edited
                else "the chat step above" if chat_read else "the client"
            )  # fmt: skip
            source = {"llm": "the language model", "request": request_source,
                      "none": "nobody (unfiltered)"}.get(r["source"], r["source"])  # fmt: skip
            searches += 1
            cached = " (cached)" if r.get("cached") else ""
            if searches > 1:
                out.append("\nClosest-matches search (nothing matched exactly; only the kind")
                out.append("of item is kept, ranked by the same words):")
            else:
                out.append(f'\nQuery: "{r["query"]}"')
                out.append(f"1. Understood by {source}{cached}")
            out.append(f"   Filters applied in SQL: {describe_filters(r.get('filters'))}")
            if r.get("guard_notes"):
                out.append(f"   Guards changed: {'; '.join(r['guard_notes'])}")
            if r.get("error"):
                out.append(f"   Extraction failed, so the search ran unfiltered: {r['error']}")
        elif event == "search.retrieve":
            c = r.get("candidates", {})
            words = f' for "{r["keyword_text"]}"' if r.get("keyword_text") else ""
            line = f"2. Retrieved ({r['mode']}): {c.get('vector', 0)} matching listings by meaning"
            if words:
                line += f", {c.get('keyword', 0)} by exact words{words}"
                line += f", fused with RRF (k={r['rrf_k']})"
            elif "keyword" in c:
                line += " (no exact-word terms, so the order is by meaning)"
            out.append(line + f"; {r['fused']} candidates kept")
        elif event == "search.rerank":
            if r.get("error"):
                out.append(f"3. Rerank failed, retrieval order kept: {r['error']}")
            else:
                cached = ", cached" if r.get("cached") else ""
                out.append(f"3. Reranked by {r['model']}: placed {r['ranked']} of "
                           f"{r['candidates']} candidates{cached}")  # fmt: skip
        elif event == "search.results":
            if r["count"] == 0:
                out.append("4. Results: none. No listing passes all of these filters.")
            else:
                out.append(f"4. Results ({r['count']}): each one passed every filter above, "
                           "and is here because of these ranks:")  # fmt: skip
            for item in r["results"]:
                ranks = item.get("ranks", {})
                why = []
                if "vector" in ranks:
                    why.append(f"#{ranks['vector']} by meaning")
                if "keyword" in ranks:
                    why.append(f"#{ranks['keyword']} by exact words")
                elif "vector" in ranks:
                    why.append("not in the exact-word list")
                if "rerank" in ranks:
                    why.append(f"reranked to #{ranks['rerank']}")
                out.append(f"   {item['position']:>2}. {item['external_id']}  {item['title']}")
                out.append(f"       {', '.join(why) or 'vector order'}")
            t = r.get("timings_ms", {})
            out.append(f"   Search time: {t.get('total', '?')} ms ({json.dumps(t)})")
        elif event == "chat.turn":
            notes = ", ".join(r.get("merge_notes") or []) or "new search"
            out.append(f"\nChat turn {r['turn']} (session {r['session']}): {notes}; "
                       f"search text \"{r['search_query']}\"")  # fmt: skip
            if r.get("no_match"):
                out.append(f"   No exact match. Counts without one filter: {r['relaxations']}")
            g = r.get("grounding", {})
            out.append(f"   Reply: {r.get('answer_source')}"
                       f"{' (cached)' if r.get('answer_cached') else ''}; recommended "
                       f"{r.get('cited_ids')}; sentences removed by the grounding check: "
                       f"{g.get('removed_sentences', 0)}")  # fmt: skip
            if r.get("answer_error"):
                out.append(f"   Reply model failed, template used: {r['answer_error']}")
        elif event == "request.rate_limited":
            out.append(f"\nRefused by the per-IP rate limit ({r['path']}); the client was told "
                       f"to retry in {r['retry_after_s']} s. Nothing was searched.")  # fmt: skip
        elif event == "chat.nearby":
            misses = {x["id"]: x["misses"] for x in r.get("listings", [])}
            out.append(f"   Closest matches (filters kept: {describe_filters(r.get('filters'))}): "
                       f"{misses}")  # fmt: skip
    errors = [r for r in records if r.get("request_id") == request_id and r["level"] == "ERROR"]
    for e in errors:
        out.append(f"\nERROR {e['logger']}: {e['msg']}")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("request_id", nargs="?", help="the x-request-id of the search")
    parser.add_argument("--last", action="store_true", help="the most recent search instead")
    parser.add_argument("--log", help="log file (default: LOG_FILE from backend/.env)")
    args = parser.parse_args()
    path = Path(args.log or get_settings().log_file or "")
    if not path.is_file():
        print("No log file. Set LOG_FILE in backend/.env (or pass --log) and restart the backend.")
        return 1
    records = load(path)
    request_id = args.request_id
    if args.last:
        searches = [r for r in records if r.get("event") == "search.results"]
        if not searches:
            print("No searches in the log yet.")
            return 1
        request_id = searches[-1]["request_id"]
    if not request_id:
        parser.error("give a request ID or --last")
    sys.stdout.reconfigure(encoding="utf-8")
    print(explain(request_id, records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
