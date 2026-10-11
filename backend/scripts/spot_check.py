"""Stage 1 acceptance report: null checks, distributions, 20 random rows -> docs/.

Usage (from backend/): .venv/Scripts/python scripts/spot_check.py
"""

import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import REPO_DIR, get_settings  # noqa: E402

REQUIRED = (
    "source", "external_id", "title", "description", "category", "price", "currency",
    "price_qar", "listing_type", "price_period", "location", "seller_name", "language",
    "search_text", "created_at",
)  # fmt: skip
REPORT = REPO_DIR / "docs" / "stage1-spot-check.md"
DATASET = REPO_DIR / "data" / "listings.jsonl"


def table(headers: list[str], rows: list[list]) -> str:
    def cell(v) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


async def main() -> int:
    settings = get_settings()
    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), statement_cache_size=0, timeout=15
    )
    try:
        total = await conn.fetchval("select count(*) from listings")
        nulls = {
            col: await conn.fetchval(f"select count(*) from listings where {col} is null")
            for col in REQUIRED
        }
        bad_condition = await conn.fetchval(
            "select count(*) from listings where condition is null "
            "and category not in ('apartments', 'villas')"
        )
        empty_text = await conn.fetchval(
            "select count(*) from listings where btrim(title) = '' or btrim(description) = ''"
        )
        dist = {
            name: await conn.fetch(
                f"select {expr} as k, count(*) as n from listings group by 1 order by 2 desc"
            )
            for name, expr in (
                ("category", "category"),
                ("condition", "coalesce(condition::text, '(null: property)')"),
                ("currency", "currency"),
                ("language", "language"),
                ("listing type / period", "listing_type || ' / ' || price_period"),
            )
        }
        prices = await conn.fetch(
            """select category, listing_type || '/' || price_period as kind, count(*) as n,
                      min(price_qar) as lo,
                      percentile_cont(0.5) within group (order by price_qar) as mid,
                      max(price_qar) as hi
               from listings group by 1, 2 order by 1, 2"""
        )
        fts = {
            q: await conn.fetchval(
                "select count(*) from listings where fts @@ plainto_tsquery($1::regconfig, $2)",
                cfg,
                q,
            )
            for q, cfg in (
                ("iphone", "english"),
                ("256gb", "english"),
                ("شقة", "arabic"),
                ("للإيجار", "arabic"),
                ("Land Cruiser", "english"),
            )  # fmt: skip
        }
        sample = await conn.fetch(
            """select id, external_id, category, title, price, currency, price_qar, condition,
                      listing_type, price_period, location, language
               from listings order by md5(external_id || 'stage1') limit 20"""
        )
    finally:
        await conn.close()

    writers = Counter()
    near_dups = 0
    for line in DATASET.open(encoding="utf-8"):
        meta = json.loads(line)["meta"]
        writers[meta["writer"]] += 1
        near_dups += bool(meta["near_duplicate_of"])

    ok = total >= 2000 and not any(nulls.values()) and not bad_condition and not empty_text
    out = [
        "# Stage 1 Spot Check",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `backend/scripts/spot_check.py`.",
        "",
        "## Acceptance",
        "",
        table(
            ["Check", "Result"],
            [
                ["Listings loaded (>= 2,000)", f"{total} {'✅' if total >= 2000 else '❌'}"],
                [
                    "Nulls in required fields",
                    f"{sum(nulls.values())} {'✅' if not any(nulls.values()) else '❌'}",
                ],
                [
                    "Condition missing outside property",
                    f"{bad_condition} {'✅' if not bad_condition else '❌'}",
                ],
                ["Empty title/description", f"{empty_text} {'✅' if not empty_text else '❌'}"],
                ["Overall", "PASS ✅" if ok else "FAIL ❌"],
            ],
        ),  # fmt: skip
        "",
        "## Distributions",
        "",
    ]
    for name, rows in dist.items():
        out += [f"**{name}**", "", table([name, "count"], [[r["k"], r["n"]] for r in rows]), ""]
    out += [
        "**text writer** (from the dataset file)",
        "",
        table(["writer", "count"], [[k, v] for k, v in writers.most_common()]),
        "",
        f"Near-duplicates: {near_dups}.",
        "",
        "## Prices (QAR, normalized)",
        "",
        table(
            ["category", "type/period", "n", "min", "median", "max"],
            [
                [
                    r["category"],
                    r["kind"],
                    r["n"],
                    f"{r['lo']:,.0f}",
                    f"{r['mid']:,.0f}",
                    f"{r['hi']:,.0f}",
                ]
                for r in prices
            ],
        ),  # fmt: skip
        "",
        "## Full-text search sanity",
        "",
        table(["query", "matches"], [[q, n] for q, n in fts.items()]),
        "",
        "## 20 random rows",
        "",
        table(
            [
                "id",
                "category",
                "title",
                "price",
                "price_qar",
                "condition",
                "type",
                "location",
                "lang",
            ],
            [
                [
                    r["id"],
                    r["category"],
                    r["title"][:70],
                    f"{r['price']:,.0f} {r['currency']}",
                    f"{r['price_qar']:,.0f}",
                    r["condition"] or "-",
                    f"{r['listing_type']}/{r['price_period']}",
                    r["location"],
                    r["language"],
                ]
                for r in sample
            ],
        ),  # fmt: skip
        "",
    ]
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"{'PASS' if ok else 'FAIL'}: {total} listings; report written to {REPORT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
