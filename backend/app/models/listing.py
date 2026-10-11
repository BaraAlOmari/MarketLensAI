"""Normalized listing: the contract between any ListingSource and the database."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

PROPERTY_CATEGORIES = frozenset({"apartments", "villas"})


class Condition(StrEnum):
    new = "new"
    like_new = "like_new"
    good = "good"
    fair = "fair"
    poor = "poor"


class ListingType(StrEnum):
    sale = "sale"
    rent = "rent"


class PricePeriod(StrEnum):
    total = "total"
    month = "month"
    year = "year"


class Language(StrEnum):
    en = "en"
    ar = "ar"
    mixed = "mixed"


class NormalizedListing(BaseModel):
    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    category: str = Field(min_length=1)
    brand: str | None = None
    model: str | None = None
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    condition: Condition | None = None
    listing_type: ListingType = ListingType.sale
    price_period: PricePeriod = PricePeriod.total
    attributes: dict[str, Any] = Field(default_factory=dict)
    location: str = Field(min_length=1)
    seller_name: str = Field(min_length=1)
    image_url: str | None = None
    language: Language
    created_at: datetime

    @model_validator(mode="after")
    def _check_consistency(self) -> "NormalizedListing":
        if self.listing_type is ListingType.sale and self.price_period is not PricePeriod.total:
            raise ValueError("sale listings must use price_period=total")
        if self.listing_type is ListingType.rent and self.price_period is PricePeriod.total:
            raise ValueError("rent listings must use price_period=month or year")
        if self.condition is None and self.category not in PROPERTY_CATEGORIES:
            raise ValueError("condition is required for non-property listings")
        return self
