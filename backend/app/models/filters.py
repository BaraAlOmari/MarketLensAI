"""Search filters (spec section 7) and the deterministic mapping from the LLM's parse.

The LLM never decides what a vague phrase means. It labels intent ("great condition",
"under 1000 riyals") in a fixed form (`QueryParse`), and `parse_to_filters` maps those labels
to hard constraints with the same rules the eval uses (eval/README.md). Changing a mapping
here therefore changes behaviour for every query, consistently, without a new LLM call.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.listing import PROPERTY_CATEGORIES, Condition, ListingType, PricePeriod

AROUND = Decimal("0.15")  # "around X" = X +/- 15%
LOW_MILEAGE_KM = 50_000  # "low mileage"
# A property price without "rent"/"sale" above this (QAR) is read as a sale price.
SALE_PRICE_THRESHOLD_QAR = Decimal("200000")


class ConditionIntent(StrEnum):
    new = "new"  # "brand new", "جديد"
    like_new = "like_new"  # "like new"
    great = "great"  # "great / excellent condition", "بحالة ممتازة"
    good = "good"  # "good condition" (at least good)
    used = "used"  # "used", "مستعمل"
    fair = "fair"  # "fair condition" (at least fair)


CONDITION_MAP: dict[ConditionIntent, list[Condition]] = {
    ConditionIntent.new: [Condition.new],
    ConditionIntent.like_new: [Condition.new, Condition.like_new],
    ConditionIntent.great: [Condition.like_new, Condition.good],
    ConditionIntent.good: [Condition.new, Condition.like_new, Condition.good],
    ConditionIntent.used: [Condition.like_new, Condition.good, Condition.fair, Condition.poor],
    ConditionIntent.fair: [Condition.new, Condition.like_new, Condition.good, Condition.fair],
}


class PriceComparator(StrEnum):
    under = "under"
    over = "over"
    around = "around"
    between = "between"


class PriceIntent(BaseModel):
    comparator: PriceComparator
    amount: Decimal = Field(gt=0)
    amount_max: Decimal | None = Field(default=None, gt=0)  # for "between"
    currency: str = "QAR"
    period: PricePeriod | None = None  # "a month", "per year"; None = not stated


class QueryParse(BaseModel):
    """The LLM's filled-in form. Every field is optional; absent means "not mentioned"."""

    model_config = ConfigDict(extra="ignore")

    category: str | None = None
    brands: list[str] = []
    models: list[str] = []
    item_types: list[str] = []
    condition: ConditionIntent | None = None
    price: PriceIntent | None = None
    listing_type: ListingType | None = None
    property_type: str | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    min_bedrooms: int | None = Field(default=None, ge=0, le=20)
    min_area_sqm: int | None = Field(default=None, gt=0)
    max_area_sqm: int | None = Field(default=None, gt=0)
    location: str | None = None
    furnished: str | None = None
    amenities: list[str] = []
    private_pool: bool | None = None
    min_year: int | None = Field(default=None, ge=1950, le=2100)
    max_year: int | None = Field(default=None, ge=1950, le=2100)
    max_mileage_km: int | None = Field(default=None, gt=0)
    low_mileage: bool | None = None
    storage_gb: int | None = Field(default=None, gt=0)
    min_ram_gb: int | None = Field(default=None, gt=0)
    gcc_specs: bool | None = None
    accident_free: bool | None = None
    delivery_available: bool | None = None
    keywords: list[str] = []


class AttributeFilter(BaseModel):
    """One condition on `listings.attributes`. Exactly one operator is set."""

    model_config = ConfigDict(extra="forbid")

    eq: Any = None
    any_of: list[str] | None = None
    min: Decimal | None = None
    max: Decimal | None = None
    contains: list[str] | None = None  # the attribute is an array holding all of these

    @model_validator(mode="after")
    def one_operator(self) -> "AttributeFilter":
        set_ops = [
            k for k in ("eq", "any_of", "min", "max", "contains") if getattr(self, k) is not None
        ]
        if not set_ops:
            raise ValueError("attribute filter needs an operator")
        if len(set_ops) > 1 and set(set_ops) != {"min", "max"}:
            raise ValueError(f"conflicting attribute operators: {set_ops}")
        return self


# Attributes the API accepts filters on (keys are also sent to SQL as bind parameters).
FILTERABLE_ATTRIBUTES = frozenset({
    "item_type", "property_type", "bedrooms", "area_sqm", "furnished", "amenities",
    "private_pool", "year", "mileage_km", "storage_gb", "ram_gb", "gcc_specs",
    "accident_free", "delivery_available",
})  # fmt: skip


class SearchFilters(BaseModel):
    """Hard constraints applied as SQL WHERE. Shown to the user as `extracted_filters`."""

    model_config = ConfigDict(extra="forbid")

    category: str | None = None
    brands: list[str] = []
    models: list[str] = []
    conditions: list[Condition] = []
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    currency: str = "QAR"
    # For rentals: the period min/max_price refer to (yearly rents compare as yearly / 12).
    price_period: PricePeriod | None = None
    listing_type: ListingType | None = None
    location: str | None = None
    attributes: dict[str, AttributeFilter] = {}
    keywords: list[str] = []  # extracted now; used by keyword search from Stage 5

    @model_validator(mode="after")
    def known_attributes(self) -> "SearchFilters":
        unknown = set(self.attributes) - FILTERABLE_ATTRIBUTES
        if unknown:
            raise ValueError(f"cannot filter on attributes: {sorted(unknown)}")
        return self

    def is_empty(self) -> bool:
        return self == SearchFilters(currency=self.currency, keywords=self.keywords)


def _price_bounds(price: PriceIntent) -> tuple[Decimal | None, Decimal | None]:
    if price.comparator is PriceComparator.under:
        return None, price.amount
    if price.comparator is PriceComparator.over:
        return price.amount, None
    if price.comparator is PriceComparator.around:
        return price.amount * (1 - AROUND), price.amount * (1 + AROUND)
    upper = price.amount_max if price.amount_max is not None else price.amount
    return min(price.amount, upper), max(price.amount, upper)


def parse_to_filters(
    parse: QueryParse, rates_to_qar: dict[str, Decimal] | None = None
) -> SearchFilters:
    """Map the LLM's labels to hard constraints. Pure and deterministic."""
    attrs: dict[str, AttributeFilter] = {}
    category = parse.category
    is_property = category in PROPERTY_CATEGORIES

    if parse.item_types:
        attrs["item_type"] = AttributeFilter(any_of=parse.item_types)
    if parse.property_type:
        attrs["property_type"] = AttributeFilter(eq=parse.property_type)
    if parse.bedrooms is not None:
        attrs["bedrooms"] = AttributeFilter(eq=parse.bedrooms)
    elif parse.min_bedrooms is not None:
        attrs["bedrooms"] = AttributeFilter(min=parse.min_bedrooms)
    if parse.min_area_sqm or parse.max_area_sqm:
        attrs["area_sqm"] = AttributeFilter(min=parse.min_area_sqm, max=parse.max_area_sqm)
    if parse.furnished:
        attrs["furnished"] = AttributeFilter(eq=parse.furnished)
    if parse.amenities:
        attrs["amenities"] = AttributeFilter(contains=parse.amenities)
    if parse.min_year or parse.max_year:
        attrs["year"] = AttributeFilter(min=parse.min_year, max=parse.max_year)
    mileage = parse.max_mileage_km or (LOW_MILEAGE_KM if parse.low_mileage else None)
    if mileage:
        attrs["mileage_km"] = AttributeFilter(max=mileage)
    if parse.storage_gb:
        attrs["storage_gb"] = AttributeFilter(eq=parse.storage_gb)
    if parse.min_ram_gb:
        attrs["ram_gb"] = AttributeFilter(min=parse.min_ram_gb)
    for flag in ("private_pool", "gcc_specs", "accident_free", "delivery_available"):
        if getattr(parse, flag) is True:  # only a stated wish; "False" means not mentioned
            attrs[flag] = AttributeFilter(eq=True)

    listing_type = parse.listing_type
    min_price = max_price = None
    period = None
    currency = parse.price.currency if parse.price else "QAR"
    if parse.price:
        min_price, max_price = _price_bounds(parse.price)
        period = parse.price.period
        if is_property and listing_type is None:
            # "villa under 2 million" is a sale; "studio under 5000" is a monthly rent.
            rate = (rates_to_qar or {}).get(currency, Decimal("1"))
            amount_qar = parse.price.amount * rate
            if period in (PricePeriod.month, PricePeriod.year):
                listing_type = ListingType.rent
            elif amount_qar >= SALE_PRICE_THRESHOLD_QAR:
                listing_type = ListingType.sale
            else:
                listing_type = ListingType.rent
        if listing_type is ListingType.rent and period in (None, PricePeriod.total):
            period = PricePeriod.month  # rents are quoted per month unless stated
        if listing_type is ListingType.sale or not is_property:
            period = None

    return SearchFilters(
        category=category,
        brands=parse.brands,
        models=parse.models,
        conditions=CONDITION_MAP[parse.condition] if parse.condition else [],
        min_price=min_price,
        max_price=max_price,
        currency=currency,
        price_period=period,
        listing_type=listing_type,
        location=parse.location,
        attributes=attrs,
        keywords=parse.keywords,
    )
