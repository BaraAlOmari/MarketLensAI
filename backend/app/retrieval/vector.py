"""Vector retrieval: nearest listings by cosine distance, optionally under SQL filters.

With filters, HNSW candidates that fail the WHERE are skipped and the scan continues
(`hnsw.iterative_scan = strict_order`, set on every pooled connection in app/db.py), so a
selective filter still returns up to `limit` rows, in exact distance order.
"""

from collections.abc import Sequence

import asyncpg

LISTING_COLUMNS = """
    id, external_id, title, description, category, brand, model, price, currency, price_qar,
    condition::text as condition, listing_type::text as listing_type,
    price_period::text as price_period, attributes, location, language, image_url
"""

# $1 query vector, $2 embedding model, $3 limit; filter parameters start at $4.
FIRST_FILTER_PARAM = 4

VECTOR_SEARCH = """
select {columns},
       1 - (embedding operator(extensions.<=>) $1::extensions.vector) as score
from listings
where {where}
order by embedding operator(extensions.<=>) $1::extensions.vector
limit $3
"""

DEFAULT_EF_SEARCH = 40  # pgvector's default hnsw.ef_search


def ef_search_for(limit: int) -> int:
    """HNSW candidate list size: at least pgvector's default (40), and >= 2x the limit."""
    return max(DEFAULT_EF_SEARCH, 2 * limit)


def vector_sql(filter_clauses: Sequence[str] = ()) -> str:
    where = " and ".join(["embedding is not null", "embedding_model = $2", *filter_clauses])
    return VECTOR_SEARCH.format(columns=LISTING_COLUMNS, where=where)


async def vector_search(
    conn: asyncpg.Connection,
    vector_literal: str,
    model: str,
    limit: int,
    filter_clauses: Sequence[str] = (),
    filter_params: Sequence = (),
) -> list[asyncpg.Record]:
    sql = vector_sql(filter_clauses)
    args = (vector_literal, model, limit, *filter_params)
    ef_search = ef_search_for(limit)
    if ef_search == DEFAULT_EF_SEARCH:
        # One round trip. Each extra statement costs ~300 ms from Qatar to the Supabase
        # region, and the pooler ignores session settings sent at connect time.
        return await conn.fetch(sql, *args)
    async with conn.transaction():
        # SET does not take bind parameters; the value is an int we computed.
        await conn.execute(f"set local hnsw.ef_search = {ef_search}")
        return await conn.fetch(sql, *args)
