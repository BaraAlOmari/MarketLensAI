"""Rerankers (Stage 6): reorder the top retrieval candidates by how well they fit the query.

Listwise LLM reranking: one call sees the query and every candidate side by side and returns
candidate numbers, best first. Unlike the embedding, the model reads the query and each
listing together, so intent words ("lightweight", "for a student") can count.

The reranker can only reorder. Numbers outside the list or repeated are discarded, and
candidates it leaves out keep their retrieval order after the ranked ones (`apply_ranking`),
so it can never add a listing or undo a filter.
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.models.search import ListingResult
from app.providers.gemini import GeminiJsonClient
from app.providers.ratelimit import SlidingWindowLimiter

SYSTEM = """You rerank search results for a marketplace in Qatar. You get a shopper's query
(English, Gulf Arabic or a mix) and numbered candidate listings. Every candidate already
passes the query's hard filters (category, price, condition, ...).

Order the candidates by how well each one fits what the shopper wants: the item they
describe, the specs they name, and intent words such as "lightweight", "for a student",
"family car", "cheap" or "with a view". Listings may be in another language than the query;
judge the meaning, not the language.

Return `ranking`: candidate numbers, best match first, at most {top_n}. Use only numbers from
the list and never repeat one."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ranking": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Candidate numbers, best match first.",
        }
    },
    "required": ["ranking"],
}

DESCRIPTION_CHARS = 160


class RerankError(RuntimeError):
    """The rerank call failed or returned nothing usable; the retrieval order is kept."""


@dataclass(frozen=True)
class Reranking:
    order: list[int]  # 0-based positions into the candidate list, best first, all included
    ranked: int  # how many positions came from the reranker (the rest keep retrieval order)
    invalid: int  # numbers the reranker returned that were out of range or repeated
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    latency_ms: float = 0.0


def candidate_text(listing: ListingResult) -> str:
    """One compact line per candidate: title, structured facts, start of the description."""
    price = f"{listing.price:,.0f} {listing.currency}"
    if listing.listing_type.value == "rent":
        price += f" per {listing.price_period.value}"
    facts = [listing.category, listing.brand or "", listing.model or "", price, listing.location]
    if listing.condition:
        facts.append(listing.condition.value.replace("_", " "))
    for key, value in listing.attributes.items():
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        facts.append(f"{key.replace('_', ' ')}: {value}")
    description = " ".join(listing.description.split())[:DESCRIPTION_CHARS]
    return f"{listing.title} | {' | '.join(f for f in facts if f)} | {description}"


def build_prompt(query: str, candidates: Sequence[str]) -> str:
    lines = [f"Query: {query}", "", "Candidates:"]
    lines += [f"[{i}] {text}" for i, text in enumerate(candidates, 1)]
    return "\n".join(lines)


def apply_ranking(count: int, numbers: Sequence[int], top_n: int) -> tuple[list[int], int, int]:
    """Turn the reranker's 1-based numbers into a full order of 0-based positions.

    Returns (order, ranked, invalid). Valid, first-seen numbers come first (at most top_n);
    every other candidate follows in its original order.
    """
    seen: list[int] = []
    invalid = 0
    for n in numbers:
        if not isinstance(n, int) or not 1 <= n <= count or (n - 1) in seen:
            invalid += 1
            continue
        if len(seen) < top_n:
            seen.append(n - 1)
    rest = [i for i in range(count) if i not in seen]
    return seen + rest, len(seen), invalid


class Reranker(ABC):
    model: str

    @property
    @abstractmethod
    def prompt_hash(self) -> str: ...

    @abstractmethod
    async def rerank(
        self, query: str, candidates: Sequence[ListingResult], top_n: int
    ) -> Reranking:
        """Order `candidates` for `query`. Raises RerankError on failure."""


class GeminiListwiseReranker(Reranker):
    def __init__(
        self,
        client: GeminiJsonClient,
        *,
        limiter: SlidingWindowLimiter,
        thinking_level: str = "minimal",
    ) -> None:
        self.client = client
        self.model = client.model
        self.thinking_level = thinking_level
        self._limiter = limiter
        blob = SYSTEM + json.dumps(SCHEMA, sort_keys=True) + thinking_level + client.api
        self._prompt_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]

    @property
    def prompt_hash(self) -> str:
        return self._prompt_hash

    async def rerank(
        self, query: str, candidates: Sequence[ListingResult], top_n: int
    ) -> Reranking:
        if not candidates:
            return Reranking([], 0, 0)
        prompt = build_prompt(query, [candidate_text(c) for c in candidates])
        await self._limiter.acquire(1)
        started = time.perf_counter()
        try:
            result = await self.client.generate_json(
                system=SYSTEM.format(top_n=top_n),
                prompt=prompt,
                schema=SCHEMA,
                thinking_level=self.thinking_level,
            )
            numbers = json.loads(result.text or "{}").get("ranking")
        except Exception as exc:
            raise RerankError(f"rerank call failed: {type(exc).__name__}") from exc
        if not isinstance(numbers, list) or not numbers:
            raise RerankError("rerank returned no ranking")
        order, ranked, invalid = apply_ranking(len(candidates), numbers, top_n)
        if ranked == 0:
            raise RerankError(f"rerank returned no valid candidate numbers ({invalid} invalid)")
        return Reranking(
            order,
            ranked,
            invalid,
            result.input_tokens,
            result.output_tokens,
            result.thought_tokens,
            round((time.perf_counter() - started) * 1000, 1),
        )
