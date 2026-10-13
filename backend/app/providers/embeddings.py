"""Embedding providers. Callers depend on `EmbeddingProvider`; Gemini is the first implementation.

Verified 2026-10-11 (ai.google.dev/gemini-api/docs/embeddings, google-genai 2.29.0):
- `gemini-embedding-2` has no `task_type`; the task goes in the text. Queries use
  `task: search result | query: ...`, documents use `title: ... | text: ...`.
- Several parts in one `contents` produce ONE aggregated embedding, and the SDK folds a
  plain list of strings into one Content. Each text must be wrapped in its own Content.
- Truncated dimensions (e.g. 1536) come back unit-normalized.
- Every text in a batch call counts as one request against RPM/RPD (measured: a batch of
  60 followed by a second batch of 60 hit the 100 RPM limit).
"""

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence

from google import genai
from google.genai import types

from app.config import Settings
from app.providers.retry import with_retries

# Measured with count_tokens on sampled listings: about 3 characters per token for English,
# Arabic and mixed text alike. 2.5 overestimates a little, which keeps pacing safe.
CHARS_PER_TOKEN_ESTIMATE = 2.5


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN_ESTIMATE)


class EmbeddingProvider(ABC):
    model: str
    dimension: int

    @abstractmethod
    async def embed_documents(
        self, texts: Sequence[str], titles: Sequence[str | None] | None = None
    ) -> list[list[float]]:
        """One vector per text, in order."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    def document_input(self, text: str, title: str | None = None) -> str:
        """The exact string sent for a document (for token estimates and caching)."""
        return text

    def query_input(self, text: str) -> str:
        return text


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str, dimension: int, timeout_s: float = 60.0) -> None:
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.dimension = dimension
        self._timeout_s = timeout_s

    def document_input(self, text: str, title: str | None = None) -> str:
        return f"title: {title or 'none'} | text: {text}"

    def query_input(self, text: str) -> str:
        return f"task: search result | query: {text}"

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []
        contents = [types.Content(parts=[types.Part.from_text(text=t)]) for t in inputs]
        config = types.EmbedContentConfig(
            output_dimensionality=self.dimension,
            http_options=types.HttpOptions(timeout=int(self._timeout_s * 1000)),
        )

        async def call():
            return await self._client.aio.models.embed_content(
                model=self.model, contents=contents, config=config
            )

        response = await with_retries(call)
        vectors = [list(e.values or []) for e in response.embeddings or []]
        if len(vectors) != len(inputs):
            raise RuntimeError(f"asked for {len(inputs)} embeddings, got {len(vectors)}")
        if any(len(v) != self.dimension for v in vectors):
            raise RuntimeError(f"embedding dimension is not {self.dimension}")
        return vectors

    async def embed_documents(
        self, texts: Sequence[str], titles: Sequence[str | None] | None = None
    ) -> list[list[float]]:
        titles = titles if titles is not None else [None] * len(texts)
        pairs = zip(texts, titles, strict=True)
        return await self._embed([self.document_input(t, h) for t, h in pairs])

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([self.query_input(text)]))[0]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider != "gemini":
        raise ValueError(f"unknown EMBEDDING_PROVIDER {settings.embedding_provider!r}")
    if settings.gemini_api_key is None:
        raise ValueError("GEMINI_API_KEY is not set")
    return GeminiEmbeddingProvider(
        settings.gemini_api_key.get_secret_value(),
        settings.embedding_model,
        settings.embedding_dimension,
    )
