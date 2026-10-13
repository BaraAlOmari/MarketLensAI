"""Query embeddings backed by a Postgres cache (migration 002).

The free tier counts every embedded text against 1,000 requests/day, so the same query never
costs twice: the exact text sent to the model is hashed, and a hit skips the API entirely.
Vectors are kept as pgvector text literals, which is also what the search SQL takes.
"""

import hashlib
from dataclasses import dataclass

import asyncpg

from app.ingestion.embed_job import to_pgvector
from app.providers.embeddings import EmbeddingProvider


def normalize_query(text: str) -> str:
    """Collapse whitespace; case and wording are kept, since both can change meaning."""
    return " ".join(text.split())


def cache_key(model: str, dimension: int, model_input: str) -> str:
    return hashlib.sha256(f"{model}|{dimension}|{model_input}".encode()).hexdigest()


@dataclass(frozen=True)
class QueryVector:
    literal: str  # pgvector text form, e.g. "[0.01,-0.2,...]"
    cached: bool
    model_input: str


class CachedQueryEmbedder:
    def __init__(self, pool: asyncpg.Pool, provider: EmbeddingProvider) -> None:
        self.pool = pool
        self.provider = provider

    @property
    def model(self) -> str:
        return self.provider.model

    def _key(self, text: str) -> tuple[str, str]:
        model_input = self.provider.query_input(normalize_query(text))
        return model_input, cache_key(self.provider.model, self.provider.dimension, model_input)

    async def lookup(self, conn: asyncpg.Connection, text: str) -> QueryVector | None:
        """Cached vector for this query, or None. Runs on the caller's connection."""
        model_input, key = self._key(text)
        literal = await conn.fetchval(
            """update query_embedding_cache set hits = hits + 1, last_used_at = now()
               where model = $1 and dimension = $2 and input_sha256 = $3
               returning embedding::text""",
            self.provider.model,
            self.provider.dimension,
            key,
        )
        return QueryVector(literal, True, model_input) if literal is not None else None

    async def embed_and_store(self, text: str) -> QueryVector:
        """Call the provider (no connection held meanwhile), then cache the vector."""
        model_input, key = self._key(text)
        literal = to_pgvector(await self.provider.embed_query(normalize_query(text)))
        async with self.pool.acquire() as conn:
            await conn.execute(
                """insert into query_embedding_cache
                       (model, dimension, input_sha256, input_text, embedding)
                   values ($1, $2, $3, $4, $5::extensions.vector)
                   on conflict (model, dimension, input_sha256) do nothing""",
                self.provider.model,
                self.provider.dimension,
                key,
                model_input,
                literal,
            )
        return QueryVector(literal, False, model_input)

    async def embed_query(self, text: str) -> QueryVector:
        async with self.pool.acquire() as conn:
            cached = await self.lookup(conn, text)
        return cached or await self.embed_and_store(text)
