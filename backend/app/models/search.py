"""Request/response schemas for POST /api/search (spec section 7)."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.filters import SearchFilters
from app.models.listing import Condition, Language, ListingType, PricePeriod


class SearchRequest(BaseModel):
    # Unknown fields are rejected rather than silently ignored.
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    # Explicit filters (e.g. edited filter chips in the UI) replace LLM extraction.
    filters: SearchFilters | None = None
    # false: skip query understanding and search unfiltered (the Stage 3 baseline).
    extract: bool = True
    # None: the server default (RETRIEVAL_MODE). "vector" reproduces Stage 4.
    retrieval: Literal["hybrid", "vector"] | None = None
    limit: int = Field(default=10, ge=1, le=50)
    debug: bool = False

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class ListingResult(BaseModel):
    id: int
    external_id: str
    title: str
    description: str
    category: str
    brand: str | None
    model: str | None
    price: Decimal
    currency: str
    price_qar: Decimal
    condition: Condition | None
    listing_type: ListingType
    price_period: PricePeriod
    attributes: dict[str, Any]
    location: str
    language: Language
    image_url: str | None
    score: float  # hybrid: RRF score; vector: cosine similarity (higher is better)
    ranks: dict[str, int] = {}  # hybrid: 1-based rank on each side ("vector", "keyword")


class ExtractionDebug(BaseModel):
    model: str
    cached: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    error: str | None  # set when extraction failed and search ran unfiltered
    parse: dict[str, Any] | None  # the LLM's raw form, before guards and mapping
    guard_notes: list[str] = []  # fields the guards dropped (scope, grounding) or filled


class SearchDebug(BaseModel):
    retrieval: str  # vector | vector+filters | hybrid | hybrid+filters
    embedding_model: str
    embedding_cached: bool
    filters_source: str  # request | llm | none
    extraction: ExtractionDebug | None = None
    candidates: dict[str, int] = {}  # hybrid: rows found per side before fusion
    timings_ms: dict[str, float]


class SearchResponse(BaseModel):
    query: str
    extracted_filters: dict[str, Any] | None = None  # the filters applied (LLM or request)
    results: list[ListingResult]
    debug: SearchDebug | None = None
