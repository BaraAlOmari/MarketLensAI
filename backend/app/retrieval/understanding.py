"""Query understanding: cached LLM extraction -> SearchFilters, never failing the search.

Lookups run on the caller's connection (one round trip). On a miss the LLM is called with no
connection held. Any failure becomes `error` on the result, and search runs unfiltered.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

import asyncpg

from app.models.filters import QueryParse, SearchFilters, parse_to_filters
from app.providers.llm import Extraction, ExtractionError, LLMProvider
from app.providers.query_cache import normalize_query
from app.providers.retry import QuotaExhaustedError
from app.retrieval.catalog import Catalog
from app.retrieval.guards import clean_parse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Understanding:
    filters: SearchFilters | None  # None: no usable extraction (search runs unfiltered)
    parse: QueryParse | None  # the LLM's form as returned (before guards)
    cached: bool
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    error: str | None = None
    guard_notes: tuple[str, ...] = ()  # fields dropped or filled by guards, invalid values


class QueryUnderstanding:
    def __init__(
        self,
        pool: asyncpg.Pool,
        llm: LLMProvider,
        catalog: Catalog,
        rates_to_qar: dict[str, Decimal],
    ) -> None:
        self.pool = pool
        self.llm = llm
        self.catalog = catalog
        self.rates = rates_to_qar

    @property
    def model(self) -> str:
        return self.llm.model

    def _key(self, query: str) -> str:
        return hashlib.sha256(normalize_query(query).encode()).hexdigest()

    def _result(
        self,
        parse: QueryParse,
        query: str,
        cached: bool,
        started: float,
        invalid: tuple[str, ...] = (),
        **tokens,
    ) -> Understanding:
        cleaned, notes = clean_parse(parse, normalize_query(query), self.catalog)
        return Understanding(
            filters=parse_to_filters(cleaned, self.rates),
            parse=parse,
            cached=cached,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            guard_notes=tuple(f"{f}:invalid value" for f in invalid) + tuple(notes),
            **tokens,
        )

    async def lookup(self, conn: asyncpg.Connection, query: str) -> Understanding | None:
        started = time.perf_counter()
        row = await conn.fetchrow(
            """update query_extraction_cache set hits = hits + 1, last_used_at = now()
               where model = $1 and prompt_hash = $2 and input_sha256 = $3
               returning parse, input_tokens, output_tokens, thought_tokens""",
            self.llm.model,
            self.llm.prompt_hash,
            self._key(query),
        )
        if row is None:
            return None
        raw = row["parse"]
        parse = QueryParse.model_validate(json.loads(raw) if isinstance(raw, str) else raw)
        return self._result(
            parse,
            query,
            True,
            started,
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            thought_tokens=row["thought_tokens"],
        )

    async def extract_and_store(self, query: str) -> Understanding:
        started = time.perf_counter()
        try:
            extraction: Extraction = await self.llm.extract_filters(normalize_query(query))
        except (ExtractionError, QuotaExhaustedError) as exc:
            logger.warning("extraction failed; searching unfiltered: %s", exc)
            return Understanding(
                filters=None,
                parse=None,
                cached=False,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
                error=str(exc) if isinstance(exc, ExtractionError) else "llm quota exhausted",
            )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """insert into query_extraction_cache
                       (model, prompt_hash, input_sha256, query_text, parse,
                        input_tokens, output_tokens, thought_tokens)
                   values ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
                   on conflict (model, prompt_hash, input_sha256) do nothing""",
                self.llm.model,
                self.llm.prompt_hash,
                self._key(query),
                normalize_query(query),
                extraction.parse.model_dump_json(exclude_defaults=True),
                extraction.input_tokens,
                extraction.output_tokens,
                extraction.thought_tokens,
            )
        return self._result(
            extraction.parse,
            query,
            False,
            started,
            invalid=extraction.invalid_fields,
            input_tokens=extraction.input_tokens,
            output_tokens=extraction.output_tokens,
            thought_tokens=extraction.thought_tokens,
        )
