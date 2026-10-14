"""Query understanding: the parse -> filters mapping, SQL building, the LLM wrapper, fallback."""

import json
from decimal import Decimal

import pytest

from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.models.filters import QueryParse, SearchFilters, parse_to_filters
from app.models.listing import Condition
from app.providers.gemini import JsonResult
from app.providers.llm import ExtractionError, GeminiLLMProvider, parse_schema
from app.retrieval.catalog import Catalog
from app.retrieval.filters_sql import MONTHLY_PRICE, build_where, escape_like
from app.retrieval.guards import bedrooms_from_query, clean_parse, numbers_in, price_from_query

CATALOG = Catalog(
    categories=("apartments", "cars", "furniture", "laptops", "phones", "villas"),
    brands=("Apple", "Google", "Samsung", "Toyota"),
    models_by_category={"phones": ("iPhone 15 Pro Max", "Pixel 10"), "cars": ("Land Cruiser",)},
    item_types=("L-shaped sofa", "office chair"),
    property_types_by_category={
        "apartments": ("apartment", "studio"),
        "villas": ("compound villa",),
    },
    locations=("Lusail", "The Pearl"),
    furnished=("furnished", "unfurnished"),
    amenities=("pool", "sea view"),
)


def filters_for(**parse) -> dict:
    """The filters a parse maps to, as the API shows them."""
    f = parse_to_filters(QueryParse(**parse), RATES)
    return f.model_dump(mode="json", exclude_defaults=True)


# Representative queries: what the LLM should label, and what that must mean as filters.
@pytest.mark.parametrize(
    ("query", "parse", "expected"),
    [
        ("used iPhone 15 Pro Max",
         {"category": "phones", "models": ["iPhone 15 Pro Max"], "condition": "used"},
         {"category": "phones", "models": ["iPhone 15 Pro Max"],
          "conditions": ["like_new", "good", "fair", "poor"]}),
        ("ايفون 16 بحالة ممتازة",
         {"category": "phones", "condition": "great"},
         {"category": "phones", "conditions": ["like_new", "good"]}),
        ("iPhone 17 Pro around $1000",
         {"category": "phones",
          "price": {"comparator": "around", "amount": 1000, "currency": "USD"}},
         {"category": "phones", "min_price": "850.00", "max_price": "1150.00", "currency": "USD"}),
        ("cheap sedan under 40k",
         {"category": "cars", "price": {"comparator": "under", "amount": 40000}},
         {"category": "cars", "max_price": "40000"}),
        ("G63 AMG ممشى قليل",
         {"category": "cars", "low_mileage": True},
         {"category": "cars", "attributes": {"mileage_km": {"max": "50000"}}}),
        ("Land Cruiser 2020 or newer",
         {"category": "cars", "min_year": 2020},
         {"category": "cars", "attributes": {"year": {"min": "2020"}}}),
        ("studio for rent under 5000 a month",
         {"category": "apartments", "listing_type": "rent", "property_type": "studio",
          "price": {"comparator": "under", "amount": 5000, "period": "month"}},
         {"category": "apartments", "listing_type": "rent", "max_price": "5000",
          "price_period": "month", "attributes": {"property_type": {"eq": "studio"}}}),
        ("villa under 2 million (no rent/sale word -> sale)",
         {"category": "villas", "price": {"comparator": "under", "amount": 2000000}},
         {"category": "villas", "listing_type": "sale", "max_price": "2000000"}),
        ("compound villa under 15000 (no rent/sale word -> monthly rent)",
         {"category": "villas", "price": {"comparator": "under", "amount": 15000}},
         {"category": "villas", "listing_type": "rent", "max_price": "15000",
          "price_period": "month"}),
        ("penthouse with sea view and pool",
         {"category": "apartments", "amenities": ["sea view", "pool"]},
         {"category": "apartments",
          "attributes": {"amenities": {"contains": ["sea view", "pool"]}}}),
        ("office chair مع توصيل",
         {"category": "furniture", "item_types": ["office chair"], "delivery_available": True},
         {"category": "furniture", "attributes": {"item_type": {"any_of": ["office chair"]},
                                                  "delivery_available": {"eq": True}}}),
        ("Range Rover not mentioning GCC (False means not asked)",
         {"category": "cars", "gcc_specs": False},
         {"category": "cars"}),
        ("2BR شقة للبيع in The Pearl",
         {"category": "apartments", "listing_type": "sale", "bedrooms": 2, "location": "The Pearl"},
         {"category": "apartments", "listing_type": "sale", "location": "The Pearl",
          "attributes": {"bedrooms": {"eq": 2}}}),
    ],
)  # fmt: skip
def test_representative_queries_map_to_filters(query, parse, expected):
    assert filters_for(**parse) == expected, query


def test_condition_mapping_matches_the_eval_readme():
    assert parse_to_filters(QueryParse(condition="like_new")).conditions == [
        Condition.new,
        Condition.like_new,
    ]
    assert parse_to_filters(QueryParse(condition="good")).conditions == [
        Condition.new,
        Condition.like_new,
        Condition.good,
    ]
    assert parse_to_filters(QueryParse(condition="new")).conditions == [Condition.new]


def test_rent_price_on_non_property_ignores_period():
    f = parse_to_filters(
        QueryParse(
            category="phones", price={"comparator": "under", "amount": 900, "period": "month"}
        )
    )
    assert f.price_period is None and f.listing_type is None


# --- SQL ---------------------------------------------------------------------------------


def test_build_where_numbers_parameters_and_converts_currency():
    filters = SearchFilters(
        category="phones",
        models=["iPhone 15 Pro Max"],
        conditions=["new"],
        max_price=Decimal("1000"),
        currency="USD",
        attributes={"storage_gb": {"eq": 512}},
    )
    clauses, params = build_where(filters, RATES, first_param=4)
    sql = " and ".join(clauses)
    assert "category = $4" in sql and "model = any($5::text[])" in sql
    assert "condition = any($6::listing_condition[])" in sql
    assert "price_qar <= $7" in sql
    assert params[3] == Decimal("3640.00")  # 1000 USD in QAR
    assert "attributes -> $8 = $9::jsonb" in sql and params[4:] == ["storage_gb", "512"]
    assert len(params) == 6


def test_build_where_monthly_rent_and_location():
    filters = SearchFilters(
        category="apartments",
        listing_type="rent",
        max_price=Decimal("8000"),
        price_period="month",
        location="The_Pearl%",
    )
    clauses, params = build_where(filters, RATES, first_param=1)
    sql = " and ".join(clauses)
    assert f"{MONTHLY_PRICE} <= $4" in sql
    assert "listing_type = $2::listing_type" in sql
    assert params[2] == "%The\\_Pearl\\%%"  # LIKE wildcards in user text are escaped
    assert "attributes ->> 'neighborhood' ilike $3" in sql


def test_build_where_ranges_are_numeric_safe():
    filters = SearchFilters(attributes={"mileage_km": {"max": 50000}, "year": {"min": 2020}})
    clauses, _ = build_where(filters, RATES, first_param=4)
    assert all("jsonb_typeof" in c for c in clauses)


def test_unknown_currency_is_rejected():
    from app.currency import UnknownCurrencyError

    with pytest.raises(UnknownCurrencyError):
        build_where(SearchFilters(max_price=Decimal("1"), currency="EUR"), RATES, 4)


def test_escape_like():
    assert escape_like("50%_off\\") == "50\\%\\_off\\\\"


# --- LLM wrapper ---------------------------------------------------------------------------


class FakeClient:
    model = "fake-lite"

    def __init__(self, text: str = "{}", error: Exception | None = None) -> None:
        self.text, self.error, self.calls = text, error, []

    async def generate_json(self, *, system, prompt, schema, thinking_level="low"):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        if self.error:
            raise self.error
        return JsonResult(self.text, 120, 30, 0)


def provider(client) -> GeminiLLMProvider:
    return GeminiLLMProvider(client, CATALOG, ["QAR", "USD"], rpm_limit=1000)


async def test_extraction_sanitizes_values_outside_the_catalog():
    text = json.dumps(
        {"category": "boats", "models": ["iPhone 15 Pro Max", "iPhone 99"], "location": "Mars",
         "condition": "used", "keywords": [" 512GB ", ""]}
    )  # fmt: skip
    out = await provider(FakeClient(text)).extract_filters("used iPhone 15 Pro Max 512GB")
    assert out.parse.category is None and out.parse.location is None
    assert out.parse.models == ["iPhone 15 Pro Max"]
    assert out.parse.keywords == ["512GB"]
    assert (out.input_tokens, out.output_tokens) == (120, 30)


async def test_extraction_errors_are_wrapped():
    with pytest.raises(ExtractionError):
        await provider(FakeClient(error=TimeoutError())).extract_filters("x")
    with pytest.raises(ExtractionError):
        await provider(FakeClient("not json")).extract_filters("x")
    with pytest.raises(ExtractionError):
        await provider(FakeClient("[1, 2]")).extract_filters("x")


async def test_one_invalid_field_loses_only_that_field():
    text = '{"category": "phones", "price": {"amount": -5}, "bedrooms": 15000, "condition": "used"}'
    out = await provider(FakeClient(text)).extract_filters("used phone")
    assert out.parse.category == "phones" and out.parse.condition == "used"
    assert out.parse.price is None and out.parse.bedrooms is None
    assert set(out.invalid_fields) == {"price", "bedrooms"}


# --- guards ------------------------------------------------------------------------------


def guard(query: str, **parse) -> tuple[dict, list[str]]:
    cleaned, dropped = clean_parse(QueryParse(**parse), query, CATALOG)
    return cleaned.model_dump(exclude_defaults=True), dropped


def test_numbers_in_reads_how_people_write_numbers():
    found = numbers_in("under 40k, 1TB, ١٥٠٠ ريال, 30 الف, 150,000 km, غرفتين, 1.5 million")
    assert {40, 40000, 1, 1024, 1500, 30, 30000, 150000, 2, 1.5, 1500000} <= found


def test_guards_drop_fields_from_other_categories_and_ungrounded_numbers():
    # Seen in the first Stage 4 run: "studio for rent" came back with storage_gb = 512.
    cleaned, dropped = guard(
        "studio for rent", category="apartments", property_type="studio", storage_gb=512
    )
    assert cleaned == {"category": "apartments", "property_type": "studio"}
    assert dropped == ["storage_gb:not for apartments"]
    # "office chair with delivery" came back with a location and a year it never mentioned.
    cleaned, dropped = guard(
        "office chair with delivery", category="furniture", item_types=["office chair"],
        delivery_available=True, location="Lusail", min_year=2020,
    )  # fmt: skip
    assert cleaned == {"category": "furniture", "item_types": ["office chair"],
                       "delivery_available": True}  # fmt: skip
    assert set(dropped) == {"min_year:not for furniture", "location:not named in query"}


def test_guards_keep_grounded_values():
    cleaned, dropped = guard(
        "2 bedroom flat in Lusail under 8k a month", category="apartments", bedrooms=2,
        location="Lusail", price={"comparator": "under", "amount": 8000, "period": "month"},
    )  # fmt: skip
    assert dropped == [] and cleaned["bedrooms"] == 2 and cleaned["location"] == "Lusail"
    # Arabic place names cannot be compared against the English catalog value: trusted.
    _, dropped = guard("شقة في لوسيل", category="apartments", location="Lusail")
    assert dropped == []


def test_guards_drop_ungrounded_price_condition_on_property_and_foreign_models():
    _, dropped = guard("Land Cruiser 2020 or newer", category="cars", models=["Land Cruiser"],
                       min_year=2020, price={"comparator": "around", "amount": 1000})  # fmt: skip
    assert dropped == ["price:amount not in query"]
    _, dropped = guard("used villa", category="villas", condition="used")
    assert dropped == ["condition:not for villas"]
    cleaned, dropped = guard("pixel", category="cars", models=["Pixel 10", "Land Cruiser"])
    assert cleaned["models"] == ["Land Cruiser"] and dropped == ["models:1 not in cars"]
    _, dropped = guard("villa", category="villas", property_type="studio")
    assert dropped == ["property_type:not a villas type"]


async def test_previous_state_goes_into_the_prompt():
    client = FakeClient()
    await provider(client).extract_filters("cheaper", SearchFilters(category="phones"))
    assert '"category":"phones"' in client.calls[0]["prompt"]
    assert client.calls[0]["prompt"].endswith("New message: cheaper")


def test_schema_uses_catalog_enums_and_no_rejected_keywords():
    schema = parse_schema(CATALOG, ["QAR", "USD"])
    text = json.dumps(schema)
    assert "maxItems" not in text and "additionalProperties" not in text
    assert schema["properties"]["location"]["enum"] == ["Lusail", "The Pearl"]
    assert schema["properties"]["price"]["properties"]["currency"]["enum"] == ["QAR", "USD"]


def test_prompt_hash_changes_with_the_catalog():
    a = provider(FakeClient()).prompt_hash
    other = Catalog(**{**CATALOG.__dict__, "locations": ("Lusail",)})
    b = GeminiLLMProvider(FakeClient(), other, ["QAR", "USD"], rpm_limit=1000).prompt_hash
    assert a != b


def test_sizes_need_a_unit_and_storage_must_be_realistic():
    # Seen in the Stage 4 runs: "Dell XPS 13" -> storage 13, "16GB RAM" -> storage 16.
    assert guard("Dell XPS 13 like new", category="laptops", storage_gb=13)[1] == [
        "storage_gb:size not written with GB/TB"
    ]
    assert guard("MacBook Air with 16GB RAM", category="laptops", storage_gb=16)[1] == [
        "storage_gb:under 32 GB is not a storage size"
    ]
    assert guard("MacBook Air with 16GB RAM", category="laptops", min_ram_gb=16)[1] == []
    assert guard("MacBook Pro 1TB", category="laptops", storage_gb=1024)[1] == []


def test_arabic_place_names_are_checked_too():
    # "office chair مع توصيل" came back with location = Lusail.
    assert guard("office chair مع توصيل", category="furniture", location="Lusail")[1] == [
        "location:not named in query"
    ]
    assert guard("فيلا للبيع في لوسيل", category="villas", location="Lusail")[1] == []


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("compound villa for rent under 15000 a month", ("under", 15000, "QAR", "month")),
        ("iPhone 14 نظيف أقل من 1500 ريال", ("under", 1500, "QAR", None)),
        ("iPhone 17 Pro around $1000", ("around", 1000, "USD", None)),
        ("sedan under 40k", ("under", 40000, "QAR", None)),
        ("villa approx 2.5 million", ("around", 2500000, "QAR", None)),
        ("سيارة اقل من 30 الف", ("under", 30000, "QAR", None)),
        ("flat over 8000 per year", ("over", 8000, "QAR", "year")),
    ],
)
def test_price_backstop_reads_explicit_limits(query, expected):
    price = price_from_query(query)
    got = (price.comparator.value, float(price.amount), price.currency,
           price.period.value if price.period else None)  # fmt: skip
    assert got == expected


@pytest.mark.parametrize(
    "query",
    ["SUV with less than 50,000 km", "laptop under 16GB", "villa over 400 sqm", "Toyota 2020"],
)
def test_price_backstop_ignores_numbers_with_other_units(query):
    assert price_from_query(query) is None


def test_backstops_fill_only_empty_fields():
    # The model put "under 15000 a month" everywhere except price (2026-10-14 run).
    cleaned, notes = guard(
        "compound villa for rent under 15000 a month", category="villas", listing_type="rent",
        max_area_sqm=15000, storage_gb=15000,
    )  # fmt: skip
    assert "max_area_sqm:area not written with sqm/متر" in notes
    assert "price:filled from query" in notes
    assert float(cleaned["price"]["amount"]) == 15000 and cleaned["price"]["period"] == "month"
    cleaned, notes = guard("شقة غرفتين للإيجار في لوسيل", category="apartments")
    assert cleaned["bedrooms"] == 2 and notes == ["bedrooms:filled from query"]
    # An LLM price is kept as is; bedrooms are not filled for non-property categories.
    cleaned, notes = guard("phone under 900", category="phones",
                           price={"comparator": "under", "amount": 900})  # fmt: skip
    assert notes == []
    assert bedrooms_from_query("2 bedroom villa") == 2 and bedrooms_from_query("studio") is None
