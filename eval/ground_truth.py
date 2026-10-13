"""Ground truth for the eval set: which listings satisfy each query's `relevant` spec.

Relevance is decided from the generator's structured facts in data/listings.jsonl (category,
model, condition, price, attributes, ...), never from listing text, so it does not depend on
how the text was written. `violations()` is also used to label why a retrieved listing was
wrong (the failure categories in docs/results.md).

Usage (from backend/): .venv/Scripts/python ../eval/ground_truth.py   # writes ground_truth.json
"""

import json
import sys
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_DIR = EVAL_DIR.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
from app.config import DEFAULT_FX_RATES_TO_QAR  # noqa: E402

QUERIES = EVAL_DIR / "queries.json"
DATASET = REPO_DIR / "data" / "listings.jsonl"
OUTPUT = EVAL_DIR / "ground_truth.json"

AROUND = Decimal("0.15")  # "around X" = X +/- 15% (eval/README.md)
MAX_RELEVANT = 150  # a query matching more than this is too vague to measure anything


def load_queries(path: Path = QUERIES) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["queries"]


def load_facts(path: Path = DATASET) -> dict[str, dict]:
    """external_id -> listing facts (the `meta` block holds the generator's price_qar)."""
    facts = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        facts[record["external_id"]] = record
    return facts


def price_bounds_qar(price: dict) -> tuple[Decimal | None, Decimal | None]:
    rate = DEFAULT_FX_RATES_TO_QAR[price.get("currency", "QAR")]
    if "around" in price:
        mid = Decimal(str(price["around"])) * rate
        return mid * (1 - AROUND), mid * (1 + AROUND)
    lo = Decimal(str(price["min"])) * rate if "min" in price else None
    hi = Decimal(str(price["max"])) * rate if "max" in price else None
    return lo, hi


def comparable_price_qar(listing: dict, basis: str | None) -> Decimal:
    """Price in QAR; with basis="month", yearly rents are compared as yearly / 12."""
    price = Decimal(listing["meta"]["price_qar"])
    if basis == "month" and listing["price_period"] == "year":
        return price / 12
    return price


def attr_ok(value, rule) -> bool:
    if value is None:
        return False  # unknown (the generator dropped it) never counts as a match
    if isinstance(rule, dict):
        if "min" in rule and value < rule["min"]:
            return False
        if "max" in rule and value > rule["max"]:
            return False
        if "in" in rule and value not in rule["in"]:
            return False
        return "contains" not in rule or rule["contains"] in value
    return value == rule


def violations(listing: dict, spec: dict) -> list[str]:
    """Names of the constraints this listing breaks; empty means relevant."""
    out = []
    categories = spec["category"] if isinstance(spec["category"], list) else [spec["category"]]
    if listing["category"] not in categories:
        return ["category"]  # everything else is meaningless across categories
    if "brands" in spec and listing["brand"] not in spec["brands"]:
        out.append("brand")
    if "models" in spec and listing["model"] not in spec["models"]:
        out.append("model")
    if "conditions" in spec and listing["condition"] not in spec["conditions"]:
        out.append("condition")
    if "listing_type" in spec and listing["listing_type"] != spec["listing_type"]:
        out.append("rent_sale")
    if "location" in spec:
        needle = spec["location"].lower()
        places = [listing["location"], listing["attributes"].get("neighborhood") or ""]
        if not any(needle in p.lower() for p in places):
            out.append("location")
    if "price" in spec:
        lo, hi = price_bounds_qar(spec["price"])
        price = comparable_price_qar(listing, spec["price"].get("basis"))
        if (lo is not None and price < lo) or (hi is not None and price > hi):
            out.append("price")
    for key, rule in spec.get("attrs", {}).items():
        if not attr_ok(listing["attributes"].get(key), rule):
            out.append(f"attr:{key}")
    return out


def relevant_ids(spec: dict, facts: Iterable[dict]) -> list[str]:
    return sorted(f["external_id"] for f in facts if not violations(f, spec))


def build(queries: list[dict], facts: dict[str, dict]) -> dict[str, list[str]]:
    return {q["id"]: relevant_ids(q["relevant"], facts.values()) for q in queries}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    queries, facts = load_queries(), load_facts()
    truth = build(queries, facts)
    problems = []
    for q in queries:
        n = len(truth[q["id"]])
        flag = ""
        if n == 0:
            flag = "  <- EMPTY"
            problems.append(q["id"])
        elif n > MAX_RELEVANT:
            flag = "  <- TOO BROAD"
            problems.append(q["id"])
        print(f"{q['id']:6} {n:4} relevant  {q['query']}{flag}")
    if problems:
        print(f"FAIL: fix these queries before using the set: {', '.join(problems)}")
        return 1
    OUTPUT.write_text(
        json.dumps(
            {"dataset": DATASET.name, "listings": len(facts), "relevant": truth},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    sizes = sorted(len(v) for v in truth.values())
    print(
        f"OK: {len(queries)} queries; relevant per query min {sizes[0]}, "
        f"median {sizes[len(sizes) // 2]}, max {sizes[-1]}; wrote {OUTPUT.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
