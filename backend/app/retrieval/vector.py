"""Vector-only retrieval (Stage 3 baseline): nearest listings by cosine distance."""

import asyncpg

LISTING_COLUMNS = """
    id, external_id, title, description, category, brand, model, price, currency, price_qar,
    condition::text as condition, listing_type::text as listing_type,
    price_period::text as price_period, attributes, location, language, image_url
"""

VECTOR_SEARCH = f"""
select {LISTING_COLUMNS},
       1 - (embedding operator(extensions.<=>) $1::extensions.vector) as score
from listings
where embedding is not null and embedding_model = $2
order by embedding operator(extensions.<=>) $1::extensions.vector
limit $3
"""


DEFAULT_EF_SEARCH = 40  # pgvector's default hnsw.ef_search


def ef_search_for(limit: int) -> int:
    """HNSW candidate list size: at least pgvector's default (40), and >= 2x the limit."""
    return max(DEFAULT_EF_SEARCH, 2 * limit)


async def vector_search(
    conn: asyncpg.Connection, vector_literal: str, model: str, limit: int
) -> list[asyncpg.Record]:
    ef_search = ef_search_for(limit)
    if ef_search == DEFAULT_EF_SEARCH:
        # One round trip. Each extra statement costs ~300 ms from Qatar to the Supabase
        # region, and the pooler ignores session settings sent at connect time.
        return await conn.fetch(VECTOR_SEARCH, vector_literal, model, limit)
    async with conn.transaction():
        # SET does not take bind parameters; the value is an int we computed.
        await conn.execute(f"set local hnsw.ef_search = {ef_search}")
        return await conn.fetch(VECTOR_SEARCH, vector_literal, model, limit)
