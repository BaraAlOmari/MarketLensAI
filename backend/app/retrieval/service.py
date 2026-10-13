"""Search orchestration. Stage 3 baseline: embed the query, return the nearest listings."""

import json
import logging
import time

import asyncpg

from app.models.search import ListingResult, SearchDebug, SearchRequest, SearchResponse
from app.providers.query_cache import CachedQueryEmbedder
from app.retrieval.vector import vector_search

logger = logging.getLogger(__name__)


class SearchUnavailableError(RuntimeError):
    """The database or embedding provider is not configured or not reachable."""


def to_result(record: asyncpg.Record) -> ListingResult:
    row = dict(record)
    if isinstance(row["attributes"], str):  # asyncpg returns jsonb as text by default
        row["attributes"] = json.loads(row["attributes"])
    return ListingResult(**row)


class SearchService:
    def __init__(self, pool: asyncpg.Pool | None, embedder: CachedQueryEmbedder | None) -> None:
        self.pool = pool
        self.embedder = embedder

    async def search(self, request: SearchRequest) -> SearchResponse:
        if self.pool is None or self.embedder is None:
            raise SearchUnavailableError("search needs DATABASE_URL and GEMINI_API_KEY")
        model, limit = self.embedder.model, request.limit
        t0 = time.perf_counter()
        # Cache hit: lookup and search share one connection (each acquire/release costs a
        # round trip). Cache miss: no connection is held during the embedding API call.
        async with self.pool.acquire() as conn:
            vector = await self.embedder.lookup(conn, request.query)
            if vector is not None:
                t1 = time.perf_counter()
                records = await vector_search(conn, vector.literal, model, limit)
        if vector is None:
            vector = await self.embedder.embed_and_store(request.query)
            t1 = time.perf_counter()
            async with self.pool.acquire() as conn:
                records = await vector_search(conn, vector.literal, model, limit)
        t2 = time.perf_counter()

        results = [to_result(r) for r in records]
        timings = {
            "embed": round((t1 - t0) * 1000, 1),
            "retrieve": round((t2 - t1) * 1000, 1),
            "total": round((time.perf_counter() - t0) * 1000, 1),
        }
        logger.info(
            "search done",
            extra={
                "fields": {
                    "results": len(results),
                    "embedding_cached": vector.cached,
                    "timings_ms": timings,
                }
            },  # fmt: skip
        )
        debug = None
        if request.debug:
            debug = SearchDebug(
                retrieval="vector",
                embedding_model=self.embedder.model,
                embedding_cached=vector.cached,
                timings_ms=timings,
            )
        return SearchResponse(query=request.query, results=results, debug=debug)
