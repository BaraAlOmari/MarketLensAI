"""Search orchestration.

Stage 4: understand the query (cached LLM extraction -> SearchFilters), then vector search
under those filters. If extraction fails, search still runs, unfiltered.

Round trips matter (~300 ms each from the dev machine to Supabase): when both the query
embedding and the extraction are cached, lookups and search share one connection. On a miss,
the embedding and the extraction API calls run concurrently with no connection held.
"""

import asyncio
import json
import logging
import time

import asyncpg

from app.models.filters import SearchFilters
from app.models.search import (
    ExtractionDebug,
    ListingResult,
    SearchDebug,
    SearchRequest,
    SearchResponse,
)
from app.providers.query_cache import CachedQueryEmbedder, QueryVector
from app.retrieval.filters_sql import build_where
from app.retrieval.understanding import QueryUnderstanding, Understanding
from app.retrieval.vector import FIRST_FILTER_PARAM, vector_search

logger = logging.getLogger(__name__)


class SearchUnavailableError(RuntimeError):
    """The database or embedding provider is not configured or not reachable."""


def to_result(record: asyncpg.Record) -> ListingResult:
    row = dict(record)
    if isinstance(row["attributes"], str):  # asyncpg returns jsonb as text by default
        row["attributes"] = json.loads(row["attributes"])
    return ListingResult(**row)


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


class SearchService:
    def __init__(
        self,
        pool: asyncpg.Pool | None,
        embedder: CachedQueryEmbedder | None,
        understanding: QueryUnderstanding | None = None,
        rates_to_qar: dict | None = None,
    ) -> None:
        self.pool = pool
        self.embedder = embedder
        self.understanding = understanding
        self.rates = rates_to_qar or {}

    async def _retrieve(
        self,
        conn: asyncpg.Connection,
        vector: QueryVector,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[asyncpg.Record]:
        clauses, params = ([], [])
        if filters is not None:
            clauses, params = build_where(filters, self.rates, FIRST_FILTER_PARAM)
        return await vector_search(
            conn, vector.literal, self.embedder.model, limit, clauses, params
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        if self.pool is None or self.embedder is None:
            raise SearchUnavailableError("search needs DATABASE_URL and GEMINI_API_KEY")
        if request.filters is not None:
            build_where(request.filters, self.rates, FIRST_FILTER_PARAM)  # 422 before any I/O
        use_llm = request.filters is None and request.extract and self.understanding is not None
        query, limit = request.query, request.limit
        timings: dict[str, float] = {}
        t0 = time.perf_counter()

        vector: QueryVector | None = None
        understood: Understanding | None = None
        records = None
        async with self.pool.acquire() as conn:
            vector = await self.embedder.lookup(conn, query)
            if use_llm:
                understood = await self.understanding.lookup(conn, query)
            timings["cache_lookup"] = _ms(time.perf_counter() - t0)
            if vector is not None and (understood is not None or not use_llm):
                filters = request.filters or (understood.filters if understood else None)
                t1 = time.perf_counter()
                records = await self._retrieve(conn, vector, filters, limit)
                timings["retrieve"] = _ms(time.perf_counter() - t1)

        if records is None:
            t1 = time.perf_counter()
            embed_task = self.embedder.embed_and_store(query) if vector is None else None
            llm_task = (
                self.understanding.extract_and_store(query)
                if use_llm and understood is None
                else None
            )
            results = await asyncio.gather(*(t for t in (embed_task, llm_task) if t))
            if embed_task is not None:
                vector = results.pop(0)
            if llm_task is not None:
                understood = results.pop(0)
            timings["api_calls"] = _ms(time.perf_counter() - t1)
            filters = request.filters or (understood.filters if understood else None)
            t2 = time.perf_counter()
            async with self.pool.acquire() as conn:
                records = await self._retrieve(conn, vector, filters, limit)
            timings["retrieve"] = _ms(time.perf_counter() - t2)

        timings["total"] = _ms(time.perf_counter() - t0)
        results = [to_result(r) for r in records]
        applied = filters is not None and not filters.is_empty()
        logger.info(
            "search done",
            extra={"fields": {
                "results": len(results), "filters_applied": applied,
                "embedding_cached": vector.cached,
                "extraction_cached": understood.cached if understood else None,
                "extraction_error": understood.error if understood else None,
                "timings_ms": timings,
            }},
        )  # fmt: skip

        debug = None
        if request.debug:
            extraction = None
            if understood is not None:
                extraction = ExtractionDebug(
                    model=self.understanding.model,
                    cached=understood.cached,
                    latency_ms=understood.latency_ms,
                    input_tokens=understood.input_tokens,
                    output_tokens=understood.output_tokens,
                    thought_tokens=understood.thought_tokens,
                    error=understood.error,
                    guard_notes=list(understood.guard_notes),
                    parse=understood.parse.model_dump(mode="json", exclude_defaults=True)
                    if understood.parse
                    else None,
                )
            debug = SearchDebug(
                retrieval="vector+filters" if applied else "vector",
                embedding_model=self.embedder.model,
                embedding_cached=vector.cached,
                filters_source="request"
                if request.filters is not None
                else "llm"
                if use_llm
                else "none",
                extraction=extraction,
                timings_ms=timings,
            )
        return SearchResponse(
            query=query,
            extracted_filters=filters.model_dump(mode="json", exclude_defaults=True)
            if filters is not None
            else None,
            results=results,
            debug=debug,
        )
