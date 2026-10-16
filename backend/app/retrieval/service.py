"""Search orchestration.

Stage 4: understand the query (cached LLM extraction -> SearchFilters). If extraction fails,
search still runs, unfiltered.
Stage 5: retrieve with hybrid search (vector + full-text, fused with RRF), both sides under
the same filters. `retrieval="vector"` gives the Stage 4 behaviour.
Stage 6: an LLM reranks the top candidates (cached; on failure the retrieval order stays).
`rerank=false` gives the Stage 5 behaviour.

Round trips matter (~300 ms each from the dev machine to Supabase): when both the query
embedding and the extraction are cached, lookups and search share one connection. On a miss,
the embedding and the extraction API calls run concurrently with no connection held.
"""

import asyncio
import json
import logging
import time

import asyncpg

from app.logging_setup import log_event
from app.models.filters import SearchFilters
from app.models.search import (
    ExtractionDebug,
    ListingResult,
    RerankDebug,
    SearchDebug,
    SearchRequest,
    SearchResponse,
)
from app.providers.query_cache import CachedQueryEmbedder, QueryVector
from app.retrieval import hybrid
from app.retrieval.filters_sql import build_where
from app.retrieval.reranking import CachedReranker, RerankOutcome
from app.retrieval.rrf import RRF_K
from app.retrieval.understanding import QueryUnderstanding, Understanding
from app.retrieval.vector import FIRST_FILTER_PARAM, vector_search

logger = logging.getLogger(__name__)


class SearchUnavailableError(RuntimeError):
    """The database or embedding provider is not configured or not reachable."""


def to_result(
    record: asyncpg.Record, score: float | None = None, ranks: dict[str, int] | None = None
) -> ListingResult:
    row = dict(record)
    if isinstance(row["attributes"], str):  # asyncpg returns jsonb as text by default
        row["attributes"] = json.loads(row["attributes"])
    if score is not None:
        row["score"] = score
    if ranks:
        row["ranks"] = ranks
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
        *,
        retrieval_mode: str = "hybrid",
        hybrid_candidates: int = 50,
        hybrid_keywords: str = "llm",
        rrf_k: int = RRF_K,
        reranker: CachedReranker | None = None,
        rerank_candidates: int = 50,
        rerank_top_n: int = 10,
    ) -> None:
        self.pool = pool
        self.embedder = embedder
        self.understanding = understanding
        self.rates = rates_to_qar or {}
        self.retrieval_mode = retrieval_mode
        self.hybrid_candidates = hybrid_candidates
        self.rrf_k = rrf_k
        self.hybrid_keywords = hybrid_keywords
        self.reranker = reranker
        self.rerank_candidates = rerank_candidates
        self.rerank_top_n = rerank_top_n

    def _keyword_text(self, query: str, filters: SearchFilters | None) -> str:
        """Text for the full-text side. "llm": the extracted exact tokens; words the filters
        already enforce ("used", "for sale", "under 1000") are not matched a second time.
        An empty string means no full-text side (the result is then pure vector order)."""
        if self.hybrid_keywords == "query":
            return query
        return " ".join(filters.keywords) if filters is not None else ""

    async def _retrieve(
        self,
        conn: asyncpg.Connection,
        mode: str,
        query: str,
        vector: QueryVector,
        filters: SearchFilters | None,
        limit: int,
    ) -> tuple[list[ListingResult], dict[str, int]]:
        """Results best first, and how many candidates each side found."""
        model = self.embedder.model
        if mode == "vector":
            clauses, params = ([], [])
            if filters is not None:
                clauses, params = build_where(filters, self.rates, FIRST_FILTER_PARAM)
            records = await vector_search(conn, vector.literal, model, limit, clauses, params)
            return [to_result(r) for r in records], {"vector": len(records)}

        clauses, params = ([], [])
        if filters is not None:
            clauses, params = build_where(filters, self.rates, hybrid.FIRST_FILTER_PARAM)
        found = await hybrid.hybrid_search(
            conn,
            vector.literal,
            model,
            self._keyword_text(query, filters),
            max(self.hybrid_candidates, limit),
            clauses,
            params,
            k=self.rrf_k,
        )
        results = [
            to_result(found.records[f.id], score=round(f.score, 6), ranks=f.ranks)
            for f in found.fused[:limit]
        ]
        return results, {"vector": len(found.vector_ids), "keyword": len(found.keyword_ids)}

    def _log_trace(
        self,
        request: SearchRequest,
        mode: str,
        use_llm: bool,
        understood: Understanding | None,
        filters: SearchFilters | None,
        vector: QueryVector,
        candidates: dict[str, int],
        pool_results: list[ListingResult],
        reranked: RerankOutcome | None,
        results: list[ListingResult],
        timings: dict[str, float],
    ) -> None:
        """One record per pipeline step, all under the request's ID (Stage 10). Together they
        say why each result is on the page: it passed `search.understand`'s filters (SQL),
        it ranked here on meaning and on exact words (`search.retrieve`, fused with RRF), and
        the reranker put it in this position (`search.rerank`)."""
        applied = filters.model_dump(mode="json", exclude_defaults=True) if filters else None
        log_event(
            logger,
            "search.understand",
            query=request.query[:200],
            source="request" if request.filters is not None else "llm" if use_llm else "none",
            filters=applied or None,
            cached=understood.cached if understood else None,
            error=understood.error if understood else None,
            guard_notes=list(understood.guard_notes) if understood else [],
            latency_ms=understood.latency_ms if understood else 0.0,
        )
        log_event(
            logger,
            "search.retrieve",
            mode=mode,
            embedding_cached=vector.cached,
            keyword_text=self._keyword_text(request.query, filters)[:200] or None,
            candidates=candidates,  # rows found per side, under the filters, before fusion
            fused=len(pool_results),
            rrf_k=self.rrf_k,
            latency_ms=timings.get("retrieve"),
        )
        if reranked is not None:
            log_event(
                logger,
                "search.rerank",
                model=self.reranker.model,
                cached=reranked.cached,
                candidates=len(pool_results),
                ranked=reranked.ranked,  # positions set by the model; the rest keep RRF order
                invalid=reranked.invalid,
                error=reranked.error,
                latency_ms=reranked.latency_ms,
            )
        log_event(
            logger,
            "search.results",
            count=len(results),
            results=[
                {
                    "position": i,
                    "id": r.id,
                    "external_id": r.external_id,
                    "title": r.title[:60],
                    "ranks": r.ranks,  # vector, keyword (absent = not in that top list), rerank
                    "rrf_score": r.score,
                }
                for i, r in enumerate(results, 1)
            ],
            timings_ms=timings,
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        if self.pool is None or self.embedder is None:
            raise SearchUnavailableError("search needs DATABASE_URL and GEMINI_API_KEY")
        if request.filters is not None:
            build_where(request.filters, self.rates, FIRST_FILTER_PARAM)  # 422 before any I/O
        use_llm = request.filters is None and request.extract and self.understanding is not None
        mode = request.retrieval or self.retrieval_mode
        query, limit = request.query, request.limit
        rerank_on = self.reranker is not None and request.rerank is not False
        # With reranking, retrieve a deeper pool; the reranker orders it, the page is cut after.
        depth = max(limit, self.rerank_candidates) if rerank_on else limit
        top_n = max(limit, self.rerank_top_n)
        reranked: RerankOutcome | None = None
        timings: dict[str, float] = {}
        t0 = time.perf_counter()

        vector: QueryVector | None = None
        understood: Understanding | None = None
        found = None
        async with self.pool.acquire() as conn:
            vector = await self.embedder.lookup(conn, query)
            if use_llm:
                understood = await self.understanding.lookup(conn, query)
            timings["cache_lookup"] = _ms(time.perf_counter() - t0)
            if vector is not None and (understood is not None or not use_llm):
                filters = request.filters or (understood.filters if understood else None)
                t1 = time.perf_counter()
                found = await self._retrieve(conn, mode, query, vector, filters, depth)
                timings["retrieve"] = _ms(time.perf_counter() - t1)
                if rerank_on and len(found[0]) > 1:
                    reranked = await self.reranker.lookup(conn, query, found[0], top_n)

        if found is None:
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
                found = await self._retrieve(conn, mode, query, vector, filters, depth)
                if rerank_on and len(found[0]) > 1:
                    reranked = await self.reranker.lookup(conn, query, found[0], top_n)
            timings["retrieve"] = _ms(time.perf_counter() - t2)

        pool_results, candidates = found
        if rerank_on and len(pool_results) > 1 and reranked is None:  # 1 = nothing to order
            t3 = time.perf_counter()
            reranked = await self.reranker.rerank_and_store(query, pool_results, top_n)
            timings["rerank"] = _ms(time.perf_counter() - t3)
        results = (reranked.results if reranked else pool_results)[:limit]
        timings["total"] = _ms(time.perf_counter() - t0)
        applied = filters is not None and not filters.is_empty()
        self._log_trace(
            request, mode, use_llm, understood, filters, vector, candidates, pool_results,
            reranked, results, timings,
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
            stages = f"{mode}+filters" if applied else mode
            debug = SearchDebug(
                retrieval=f"{stages}+rerank" if reranked is not None else stages,
                embedding_model=self.embedder.model,
                embedding_cached=vector.cached,
                filters_source="request"
                if request.filters is not None
                else "llm"
                if use_llm
                else "none",
                extraction=extraction,
                candidates=candidates,
                rerank=RerankDebug(
                    model=self.reranker.model,
                    cached=reranked.cached,
                    latency_ms=reranked.latency_ms,
                    candidates=len(pool_results),
                    ranked=reranked.ranked,
                    invalid=reranked.invalid,
                    input_tokens=reranked.input_tokens,
                    output_tokens=reranked.output_tokens,
                    thought_tokens=reranked.thought_tokens,
                    error=reranked.error,
                )
                if reranked is not None
                else None,
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
