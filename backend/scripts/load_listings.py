"""Load a ListingSource into Postgres. Idempotent: upserts on (source, external_id).

If a row's search_text changes, its embedding is cleared so Stage 2 re-embeds it.

Usage (from backend/):
    .venv/Scripts/python scripts/load_listings.py                       # data/listings.jsonl
    .venv/Scripts/python scripts/load_listings.py --file ../data/x.jsonl
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import REPO_DIR, get_settings  # noqa: E402
from app.currency import to_qar  # noqa: E402
from app.ingestion.source import (  # noqa: E402
    ListingSource,
    SyntheticListingSource,
    build_search_text,
)

UPSERT = """
insert into listings (
    source, external_id, title, description, category, brand, model,
    price, currency, price_qar, condition, listing_type, price_period,
    attributes, location, seller_name, image_url, language, search_text, created_at
) values (
    $1, $2, $3, $4, $5, $6, $7,
    $8, $9, $10, $11::listing_condition, $12::listing_type, $13::price_period,
    $14::jsonb, $15, $16, $17, $18, $19, $20
)
on conflict (source, external_id) do update set
    title = excluded.title,
    description = excluded.description,
    category = excluded.category,
    brand = excluded.brand,
    model = excluded.model,
    price = excluded.price,
    currency = excluded.currency,
    price_qar = excluded.price_qar,
    condition = excluded.condition,
    listing_type = excluded.listing_type,
    price_period = excluded.price_period,
    attributes = excluded.attributes,
    location = excluded.location,
    seller_name = excluded.seller_name,
    image_url = excluded.image_url,
    language = excluded.language,
    search_text = excluded.search_text,
    created_at = excluded.created_at,
    embedding = case when listings.search_text is distinct from excluded.search_text
                     then null else listings.embedding end,
    embedding_model = case when listings.search_text is distinct from excluded.search_text
                           then null else listings.embedding_model end,
    updated_at = now()
"""

BATCH_SIZE = 250


def to_rows(source: ListingSource, rates) -> list[tuple]:
    rows = []
    for item in source.iter_listings():
        rows.append(
            (
                source.name,
                item.external_id,
                item.title,
                item.description,
                item.category,
                item.brand,
                item.model,
                item.price,
                item.currency,
                to_qar(item.price, item.currency, rates),
                item.condition.value if item.condition else None,
                item.listing_type.value,
                item.price_period.value,
                json.dumps(item.attributes, ensure_ascii=False),
                item.location,
                item.seller_name,
                item.image_url,
                item.language.value,
                build_search_text(item),
                item.created_at,
            )
        )
    return rows


async def main(path: Path) -> int:
    settings = get_settings()
    if settings.database_url is None:
        print("FAIL: DATABASE_URL is not set")
        return 1
    started = time.perf_counter()
    rows = to_rows(SyntheticListingSource(path), settings.fx_rates_to_qar)
    print(f"OK: validated {len(rows)} listings from {path}")

    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), statement_cache_size=0, timeout=15
    )
    try:
        async with conn.transaction():
            for i in range(0, len(rows), BATCH_SIZE):
                await conn.executemany(UPSERT, rows[i : i + BATCH_SIZE])
        total = await conn.fetchval("select count(*) from listings where source = 'synthetic'")
    finally:
        await conn.close()
    print(
        f"OK: upserted {len(rows)} rows in {time.perf_counter() - started:.1f}s; table has {total}"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=REPO_DIR / "data" / "listings.jsonl")
    sys.exit(asyncio.run(main(parser.parse_args().file)))
