"""Hybrid retrieval (Stage 5): vector search + Postgres full-text search, fused with RRF.

One round trip fetches up to `depth` candidates from each side, both under the same SQL
filters, and returns their rows. Python ranks each side and fuses them (app/retrieval/rrf.py).

Full-text side: the listing's `fts` column is english || arabic tsvectors (migration 001). The
query is normalised the same way and its lexemes are OR-ed, so a listing matching some of the
words still counts, and ts_rank orders by how many match. ts_rank has no idea how rare a word
is (no IDF), so common words ("used", "في") count as much as rare ones ("Lusail"); fusing with
the vector side is what keeps that noise down.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg

from app.retrieval.rrf import RRF_K, Fused, rrf_merge
from app.retrieval.vector import LISTING_COLUMNS

# $1 query vector, $2 embedding model, $3 candidates per side, $4 query text; filters from $5.
FIRST_FILTER_PARAM = 5

# Lexemes of the query under both configs, OR-ed: 'samsung' | 's24' | 'ultra' | '512gb'.
QUERY_TSQUERY = """(
    select nullif(string_agg(quote_literal(lexeme), ' | '), '')::tsquery
    from unnest(tsvector_to_array(
        to_tsvector('english', $4) || to_tsvector('arabic', $4))) as lexeme
)"""

HYBRID_SEARCH = """
with vec as (
    select id, 1 - (embedding operator(extensions.<=>) $1::extensions.vector) as similarity
    from listings
    where {vec_where}
    order by embedding operator(extensions.<=>) $1::extensions.vector
    limit $3
),
tsq as (select {tsquery} as q),
kw as (
    select listings.id, ts_rank(listings.fts, tsq.q) as kw_score
    from listings, tsq
    where {kw_where}
    order by kw_score desc,
             listings.embedding operator(extensions.<=>) $1::extensions.vector, listings.id
    limit $3
),
hits as (
    select coalesce(vec.id, kw.id) as hit_id, vec.similarity, kw.kw_score
    from vec full join kw on kw.id = vec.id
)
select {columns}, hits.similarity, hits.kw_score,
       1 - (listings.embedding operator(extensions.<=>) $1::extensions.vector) as meaning
from hits join listings on listings.id = hits.hit_id
"""


def hybrid_sql(filter_clauses: Sequence[str] = ()) -> str:
    vec_where = " and ".join(["embedding is not null", "embedding_model = $2", *filter_clauses])
    kw_where = " and ".join(["tsq.q is not null", "listings.fts @@ tsq.q", *filter_clauses])
    return HYBRID_SEARCH.format(
        vec_where=vec_where, kw_where=kw_where, tsquery=QUERY_TSQUERY, columns=LISTING_COLUMNS
    )


@dataclass(frozen=True)
class HybridResult:
    records: dict[int, asyncpg.Record]  # by listing id
    fused: list[Fused]  # best first; ranks hold "vector" and/or "keyword"
    vector_ids: list[int]
    keyword_ids: list[int]


def rank_sides(records: Sequence[asyncpg.Record]) -> tuple[list[int], list[int]]:
    """Order each side best first, deterministically."""
    vec = [r for r in records if r["similarity"] is not None]
    kw = [r for r in records if r["kw_score"] is not None]
    vector_ids = [r["id"] for r in sorted(vec, key=lambda r: (-r["similarity"], r["id"]))]
    # ts_rank ties are common (many listings share the same matched words); break them by
    # meaning rather than by id, so the keyword list does not inject an arbitrary order.
    keyword_ids = [
        r["id"] for r in sorted(kw, key=lambda r: (-r["kw_score"], -(r["meaning"] or 0), r["id"]))
    ]
    return vector_ids, keyword_ids


async def hybrid_search(
    conn: asyncpg.Connection,
    vector_literal: str,
    model: str,
    query_text: str,
    depth: int,
    filter_clauses: Sequence[str] = (),
    filter_params: Sequence = (),
    k: int = RRF_K,
) -> HybridResult:
    records = await conn.fetch(
        hybrid_sql(filter_clauses), vector_literal, model, depth, query_text, *filter_params
    )
    vector_ids, keyword_ids = rank_sides(records)
    fused = rrf_merge({"vector": vector_ids, "keyword": keyword_ids}, k=k)
    return HybridResult({r["id"]: r for r in records}, fused, vector_ids, keyword_ids)
