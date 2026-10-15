"""Ground truth for the multi-turn eval (eval/conversations.json).

A scored turn's relevant set uses the same `relevant` spec grammar as the single-turn eval.
`cheaper_than_turn: N` adds one rule: comparable price (QAR, yearly rent / 12) strictly below
the median of turn N's relevant set. The median comes from the *correct* listings of turn N,
not from what the system showed, so the ground truth does not depend on the system.

Usage (from backend/): .venv/Scripts/python ../eval/conversations.py   # counts per scored turn
"""

import json
import statistics
import sys
from decimal import Decimal
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))
from ground_truth import load_facts, violations  # noqa: E402

CONVERSATIONS = EVAL_DIR / "conversations.json"


def load_conversations(path: Path = CONVERSATIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["conversations"]


def comparable_price(listing: dict) -> Decimal:
    price = Decimal(listing["meta"]["price_qar"])
    return price / 12 if listing["price_period"] == "year" else price


def turn_violations(listing: dict, turn: dict, medians: dict[int, Decimal]) -> list[str]:
    out = violations(listing, turn["relevant"])
    n = turn.get("cheaper_than_turn")
    if n is not None and not out and comparable_price(listing) >= medians[n]:
        out.append("cheaper")
    return out


def conversation_truth(conv: dict, facts: dict[str, dict]) -> dict[int, list[str]]:
    """1-based turn number -> relevant external ids, for every turn with a `relevant` spec."""
    truth: dict[int, list[str]] = {}
    medians: dict[int, Decimal] = {}
    for number, turn in enumerate(conv["turns"], 1):
        if "relevant" not in turn:
            continue
        ids = sorted(x for x, f in facts.items() if not turn_violations(f, turn, medians))
        truth[number] = ids
        if ids:
            medians[number] = statistics.median(comparable_price(facts[x]) for x in ids)
    return truth


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    facts = load_facts()
    problems = []
    for conv in load_conversations():
        truth = conversation_truth(conv, facts)
        for number, ids in truth.items():
            msg = conv["turns"][number - 1]["message"]
            flag = "  <- EMPTY" if not ids else ""
            if not ids:
                problems.append(f"{conv['id']} turn {number}")
            print(f"{conv['id']} turn {number}: {len(ids):4} relevant  {msg}{flag}")
    if problems:
        print("FAIL: empty scored turns: " + ", ".join(problems))
        return 1
    print("OK: every scored turn has relevant listings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
