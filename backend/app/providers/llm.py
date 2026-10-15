"""LLM providers. Stage 4: `extract_filters` turns a search query into a filled-in form.

The model only labels what the user said (QueryParse). It never writes SQL, never decides
what "great condition" means in conditions, and can only name catalog values (the schema's
enums), so whatever it returns is safe to map to filters.
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.models.filters import ConditionIntent, PriceComparator, QueryParse, SearchFilters
from app.models.listing import ListingType, PricePeriod
from app.providers.gemini import GeminiJsonClient
from app.providers.ratelimit import SlidingWindowLimiter
from app.retrieval.catalog import Catalog

SYSTEM = """You turn one marketplace search query into a filter form. The marketplace is in
Qatar. Queries are in English, Gulf Arabic, or a mix of both.

Fill ONLY fields the user states or clearly implies; leave every other field out. Never guess.
Most queries need two to four fields. The examples below explain formats; never copy them.
Use catalog values exactly as the schema lists them, mapping Arabic, misspelled or short names
(for example "لاندكروزر" -> "Land Cruiser", "لوسيل" -> "Lusail", "G63" -> "G 63 AMG").

- category: set it whenever the kind of item is clear. Flats, studios, penthouses and duplexes
  are "apartments"; villas and townhouses are "villas".
- models: only when the user names a model or a product line. A product line ("MacBook Air",
  "Land Cruiser Prado") means every catalog model in that line. A model name without a
  suffix means exactly that model ("iPhone 16" is not "iPhone 16 Pro"). Do not pick models
  from a use or a body type ("gaming laptop", "SUV", "sedan", "foldable", "for students").
- brands: when the user names a brand, or a platform: "android" means every phone brand in
  the catalog except Apple.
- condition: "new" for brand new / sealed / جديد; "like_new" for like new; "great" for great,
  excellent or very good condition / بحالة ممتازة; "good" for good condition; "used" for used,
  second-hand, مستعمل; "fair" for fair condition. Words like "clean" or "نظيف" alone are not a
  condition.
- price: comparator "under" (under, less than, below, max, أقل من, تحت), "over", "around"
  (around, about, approx, حوالي) or "between". amount is a plain number: "40k" = 40000,
  "1.5 million" = 1500000, "30 الف" = 30000. currency: "USD" for $ or dollars, otherwise
  "QAR" (riyal, ريال, QR, or no currency given). period: "month" for a month / monthly /
  شهري, "year" for yearly / annual / سنوي; otherwise leave it out.
- listing_type: "rent" for rent, lease, للإيجار; "sale" for sale, buy, للبيع.
- bedrooms: an exact count ("2 bedroom", "2BR", "غرفتين" = 2). "3+ bedrooms" is min_bedrooms.
  A studio is property_type "studio", not a bedroom count.
- Pools: for villas "pool" / "مسبح" means private_pool = true; for apartments it is the
  amenity "pool". "sea view" is the amenity "sea view".
- Cars: "low mileage" / "ممشى قليل" is low_mileage = true; an explicit number is
  max_mileage_km. "2020 or newer" is min_year = 2020; a single year ("2020 Land Cruiser")
  is min_year = max_year = 2020.
- storage_gb is exact ("512GB" = 512, "1TB" = 1024). min_ram_gb for RAM ("16GB RAM" = 16).
- Booleans (gcc_specs, accident_free, delivery_available, private_pool): true only when the
  user asks for it.
- keywords: up to 8 exact tokens worth keyword matching, such as model numbers and specs
  ("512GB", "M4 Max", "S24"). Not generic words."""

MAX_KEYWORDS = 8

STATE_PROMPT = """Current filters from earlier in the conversation:
{state}
The new message refines them. Return the complete updated form."""


def _enum(values, description: str | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "enum": list(values)}
    if description:
        schema["description"] = description
    return schema


def _array(items: dict[str, Any]) -> dict[str, Any]:
    # No maxItems / additionalProperties: the docs list them, but gemini-3.5-flash-lite's
    # Interactions API rejected a schema using them with HTTP 400 (2026-10-13). Limits are
    # enforced in `sanitize` instead.
    return {"type": "array", "items": items}


FIELD_DOCS = {
    "category": "Kind of item. Set it whenever it is clear from the query.",
    "brands": "Brands the user names (or implies with a platform such as android).",
    "models": "Catalog models the user names, or every model of a product line they name.",
    "item_types": "Furniture type the user names (sofa, bed, chair, table, ...).",
    "condition": "Only if the user states the item's condition.",
    "price": "Only if the user states a price, budget or price limit.",
    "listing_type": "rent or sale, only if the user says so.",
    "property_type": "Only a named sub-type: studio, penthouse, duplex, townhouse, compound "
    "villa. A plain 'apartment', 'flat' or 'villa' needs no property_type.",
    "bedrooms": "Number of bedrooms of an apartment or villa ('2 bedroom', '2BR', 'غرفتين').",
    "min_bedrooms": "Lower bound on bedrooms ('3+ bedrooms', 'at least 3 bedrooms').",
    "min_area_sqm": "Smallest floor area in square metres the user accepts.",
    "max_area_sqm": "Largest floor area in square metres the user accepts.",
    "location": "Area or city the user names.",
    "furnished": "Furnishing the user asks for (مفروش = furnished).",
    "amenities": "Apartment amenities the user asks for.",
    "private_pool": "true if the user wants a villa with a pool.",
    "min_year": "Earliest car model year the user accepts.",
    "max_year": "Latest car model year the user accepts.",
    "max_mileage_km": "Highest mileage in km the user accepts, when a number is given.",
    "low_mileage": "true if the user asks for low mileage without a number.",
    "storage_gb": "Storage of a phone or laptop, only when written with GB or TB (256GB; "
    "1TB = 1024). Never RAM, a model number, or a count of rooms.",
    "min_ram_gb": "Laptop RAM in GB, only when the user says RAM or memory.",
    "gcc_specs": "true if the user asks for GCC specs.",
    "accident_free": "true if the user asks for an accident-free car.",
    "delivery_available": "true if the user asks for delivery (توصيل).",
    "keywords": "Exact tokens worth keyword matching: model numbers and specs.",
}


def parse_schema(catalog: Catalog, currencies: list[str]) -> dict[str, Any]:
    schema = _parse_schema(catalog, currencies)
    for name, prop in schema["properties"].items():
        prop["description"] = FIELD_DOCS[name]
    return schema


def _parse_schema(catalog: Catalog, currencies: list[str]) -> dict[str, Any]:
    integer = {"type": "integer", "minimum": 0}
    boolean = {"type": "boolean"}
    return {
        "type": "object",
        "properties": {
            "category": _enum(catalog.categories),
            "brands": _array(_enum(catalog.brands)),
            "models": _array(_enum(catalog.models)),
            "item_types": _array(_enum(catalog.item_types)),
            "condition": _enum([c.value for c in ConditionIntent]),
            "price": {
                "type": "object",
                "properties": {
                    "comparator": _enum([c.value for c in PriceComparator]),
                    "amount": {"type": "number", "minimum": 0},
                    "amount_max": {"type": "number", "minimum": 0},
                    "currency": _enum(currencies),
                    "period": _enum([p.value for p in PricePeriod]),
                },
                "required": ["comparator", "amount"],
            },
            "listing_type": _enum([t.value for t in ListingType]),
            "property_type": _enum(catalog.property_types),
            "bedrooms": {**integer, "maximum": 20},
            "min_bedrooms": {**integer, "maximum": 20},
            "min_area_sqm": integer,
            "max_area_sqm": integer,
            "location": _enum(catalog.locations),
            "furnished": _enum(catalog.furnished),
            "amenities": _array(_enum(catalog.amenities)),
            "private_pool": boolean,
            "min_year": {"type": "integer", "minimum": 1950, "maximum": 2100},
            "max_year": {"type": "integer", "minimum": 1950, "maximum": 2100},
            "max_mileage_km": integer,
            "low_mileage": boolean,
            "storage_gb": integer,
            "min_ram_gb": integer,
            "gcc_specs": boolean,
            "accident_free": boolean,
            "delivery_available": boolean,
            "keywords": _array({"type": "string"}),
        },
    }


def sanitize(parse: QueryParse, catalog: Catalog) -> QueryParse:
    """Drop any value outside the catalog (the schema should prevent it; never trust it)."""

    def keep(values, allowed, limit=30):
        return list(dict.fromkeys(v for v in values if v in allowed))[:limit]

    def one(value, allowed):
        return value if value in allowed else None

    return parse.model_copy(
        update={
            "category": one(parse.category, catalog.categories),
            "brands": keep(parse.brands, catalog.brands),
            "models": keep(parse.models, catalog.models),
            "item_types": keep(parse.item_types, catalog.item_types),
            "property_type": one(parse.property_type, catalog.property_types),
            "location": one(parse.location, catalog.locations),
            "furnished": one(parse.furnished, catalog.furnished),
            "amenities": keep(parse.amenities, catalog.amenities),
            "keywords": [k.strip() for k in parse.keywords if k.strip()][:MAX_KEYWORDS],
        }
    )


class ExtractionError(RuntimeError):
    """The LLM call failed or returned something unusable; search runs unfiltered."""


def lenient_parse(text: str) -> tuple[QueryParse, list[str]]:
    """Validate field by field, so one bad value (say bedrooms = 15000) loses only that field.

    Raises ExtractionError only when the output is not a JSON object at all.
    """
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise ExtractionError("extraction is not JSON") from exc
    if not isinstance(data, dict):
        raise ExtractionError("extraction is not a JSON object")
    good: dict[str, Any] = {}
    invalid: list[str] = []
    for key, value in data.items():
        if key not in QueryParse.model_fields:
            continue
        try:
            QueryParse.model_validate({key: value})
        except ValidationError:
            invalid.append(key)
            continue
        good[key] = value
    return QueryParse.model_validate(good), invalid


@dataclass(frozen=True)
class Extraction:
    parse: QueryParse
    invalid_fields: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    latency_ms: float = 0.0


class LLMProvider(ABC):
    model: str

    @property
    @abstractmethod
    def prompt_hash(self) -> str:
        """Changes whenever the prompt, schema or catalog changes (cache key)."""

    @abstractmethod
    async def extract_filters(self, query: str, state: SearchFilters | None = None) -> Extraction:
        """Fill the filter form for `query`. Raises ExtractionError on any failure."""


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        client: GeminiJsonClient,
        catalog: Catalog,
        currencies: list[str],
        *,
        rpm_limit: int,
        thinking_level: str = "minimal",
        limiter: SlidingWindowLimiter | None = None,
    ) -> None:
        self.client = client
        self.model = client.model
        self.catalog = catalog
        self.schema = parse_schema(catalog, currencies)
        self.thinking_level = thinking_level
        # Share the limiter with anything else calling the same model (the reranker).
        self._limiter = limiter or SlidingWindowLimiter(max(1, int(rpm_limit * 0.9)))
        blob = SYSTEM + json.dumps(self.schema, sort_keys=True, ensure_ascii=False)
        blob += thinking_level + getattr(client, "api", "")  # a different API is a new cache
        self._prompt_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]

    @property
    def prompt_hash(self) -> str:
        return self._prompt_hash

    async def extract_filters(self, query: str, state: SearchFilters | None = None) -> Extraction:
        prompt = query
        if state is not None and not state.is_empty():
            state_json = state.model_dump_json(exclude_defaults=True)
            prompt = STATE_PROMPT.format(state=state_json) + "\n\nNew message: " + query
        await self._limiter.acquire(1)
        started = time.perf_counter()
        try:
            result = await self.client.generate_json(
                system=SYSTEM, prompt=prompt, schema=self.schema, thinking_level=self.thinking_level
            )
        except Exception as exc:
            raise ExtractionError(f"extraction call failed: {type(exc).__name__}") from exc
        parse, invalid = lenient_parse(result.text)
        return Extraction(
            parse=sanitize(parse, self.catalog),
            invalid_fields=tuple(invalid),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            thought_tokens=result.thought_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
