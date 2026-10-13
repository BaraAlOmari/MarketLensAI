"""Request/response schemas for POST /api/search (spec section 7)."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.listing import Condition, Language, ListingType, PricePeriod


class SearchRequest(BaseModel):
    # `filters` arrives with query understanding in Stage 4; until then unknown fields are
    # rejected rather than silently ignored.
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
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
    score: float  # cosine similarity for the vector baseline (higher is closer)


class SearchDebug(BaseModel):
    retrieval: str
    embedding_model: str
    embedding_cached: bool
    timings_ms: dict[str, float]


class SearchResponse(BaseModel):
    query: str
    extracted_filters: dict[str, Any] | None = None  # filled by query understanding (Stage 4)
    results: list[ListingResult]
    debug: SearchDebug | None = None
