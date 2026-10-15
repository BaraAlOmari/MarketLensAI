"""Cached reranking that never fails a search.

The lookup runs on the caller's connection (one round trip). On a miss the reranker is called
with no connection held. Any failure returns the retrieval order unchanged with `error` set.
"""

import hashlib
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg

from app.models.search import ListingResult
from app.providers.query_cache import normalize_query
from app.providers.rerank import Reranker, RerankError, candidate_text
from app.providers.retry import QuotaExhaustedError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankOutcome:
    results: list[ListingResult]  # reordered (or unchanged on error)
    cached: bool
    latency_ms: float
    ranked: int = 0
    invalid: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    error: str | None = None


def _with_rank(results: Sequence[ListingResult], order: Sequence[int]) -> list[ListingResult]:
    out = []
    for position, index in enumerate(order, 1):
        item = results[index]
        out.append(item.model_copy(update={"ranks": {**item.ranks, "rerank": position}}))
    return out


class CachedReranker:
    def __init__(self, pool: asyncpg.Pool, reranker: Reranker) -> None:
        self.pool = pool
        self.reranker = reranker

    @property
    def model(self) -> str:
        return self.reranker.model

    def _key(self, query: str, candidates: Sequence[ListingResult], top_n: int) -> str:
        blob = json.dumps(
            [normalize_query(query), top_n, [[c.id, candidate_text(c)] for c in candidates]],
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    async def lookup(
        self,
        conn: asyncpg.Connection,
        query: str,
        candidates: Sequence[ListingResult],
        top_n: int,
    ) -> RerankOutcome | None:
        started = time.perf_counter()
        row = await conn.fetchrow(
            """update rerank_cache set hits = hits + 1, last_used_at = now()
               where model = $1 and prompt_hash = $2 and input_sha256 = $3
               returning ranked_ids, ranked, invalid, input_tokens, output_tokens,
                         thought_tokens""",
            self.reranker.model,
            self.reranker.prompt_hash,
            self._key(query, candidates, top_n),
        )
        if row is None:
            return None
        position = {c.id: i for i, c in enumerate(candidates)}
        order = [position[i] for i in row["ranked_ids"] if i in position]
        if len(order) != len(candidates):
            return None  # should not happen (the key covers the ids); recompute to be safe
        return RerankOutcome(
            results=_with_rank(candidates, order),
            cached=True,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            ranked=row["ranked"],
            invalid=row["invalid"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            thought_tokens=row["thought_tokens"],
        )

    async def rerank_and_store(
        self, query: str, candidates: Sequence[ListingResult], top_n: int
    ) -> RerankOutcome:
        started = time.perf_counter()
        try:
            r = await self.reranker.rerank(normalize_query(query), candidates, top_n)
        except (RerankError, QuotaExhaustedError) as exc:
            logger.warning("rerank failed; keeping retrieval order: %s", exc)
            return RerankOutcome(
                results=list(candidates),
                cached=False,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
                error=str(exc) if isinstance(exc, RerankError) else "llm quota exhausted",
            )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """insert into rerank_cache
                       (model, prompt_hash, input_sha256, query_text, candidate_ids, ranked_ids,
                        ranked, invalid, input_tokens, output_tokens, thought_tokens)
                   values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                   on conflict (model, prompt_hash, input_sha256) do nothing""",
                self.reranker.model,
                self.reranker.prompt_hash,
                self._key(query, candidates, top_n),
                normalize_query(query),
                [c.id for c in candidates],
                [candidates[i].id for i in r.order],
                r.ranked,
                r.invalid,
                r.input_tokens,
                r.output_tokens,
                r.thought_tokens,
            )
        return RerankOutcome(
            results=_with_rank(candidates, r.order),
            cached=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            ranked=r.ranked,
            invalid=r.invalid,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            thought_tokens=r.thought_tokens,
        )
