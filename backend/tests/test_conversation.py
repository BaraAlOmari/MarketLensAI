"""Stage 8: conversation state. Merge rules, reset/cheaper detection, the session store, and
a multi-turn chat with fakes."""

from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from app.answers.chat import NEARBY_LIMIT, ChatService
from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.conversation.merge import (
    describe,
    drop_removed_keywords,
    median_price,
    merge,
    split_reset,
    wants_cheaper,
)
from app.conversation.store import Session, combine_query
from app.models.filters import SearchFilters
from app.models.search import SearchResponse
from app.providers.query_cache import QueryVector
from app.retrieval.catalog import Catalog
from app.retrieval.understanding import Understanding

CATALOG = Catalog(
    categories=("apartments", "cars", "furniture", "laptops", "phones", "villas"),
    brands=("Apple", "Samsung"),
    models_by_category={"phones": ("iPhone 15 Pro Max", "Galaxy S24 Ultra")},
    item_types=(),
    property_types_by_category={},
    locations=("Lusail",),
    furnished=(),
    amenities=(),
    brand_by_model={"iPhone 15 Pro Max": "Apple", "Galaxy S24 Ultra": "Samsung"},
)
PHONE = SearchFilters(
    category="phones", brands=["Apple"], models=["iPhone 15 Pro Max"],
    conditions=["like_new", "good", "fair", "poor"], keywords=["Pro"],
)  # fmt: skip


def dump(f: SearchFilters | None) -> dict | None:
    return f.model_dump(mode="json", exclude_defaults=True) if f else None


# --- reset / cheaper -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [("start over", (True, "")), ("Start over, show me sofas", (True, "show me sofas")),
     ("ok let's start over and look for villas", (True, "look for villas")),
     ("new search", (True, "")), ("ابدأ من جديد", (True, "")),
     ("factory reset iPhone 15", (False, "factory reset iPhone 15")),
     ("cheaper ones", (False, "cheaper ones"))],
)  # fmt: skip
def test_split_reset(message, expected):
    assert split_reset(message) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [("cheaper ones", True), ("anything cheaper?", True), ("أرخص", True),
     ("more affordable please", True), ("under 2000", False), ("512GB", False)],
)  # fmt: skip
def test_wants_cheaper(message, expected):
    assert wants_cheaper(message) is expected


# --- merge -----------------------------------------------------------------------------------


def test_follow_up_adds_and_keeps_the_rest():
    merged, notes = merge(PHONE, SearchFilters(category="phones", max_price=Decimal(2000)), CATALOG)
    assert dump(merged) == {**dump(PHONE), "max_price": "2000"}
    assert "price replaced" in notes


def test_a_new_value_replaces_the_old_one():
    first, _ = merge(PHONE, SearchFilters(max_price=Decimal(2000)), CATALOG)
    second, _ = merge(first, SearchFilters(max_price=Decimal(2500)), CATALOG)
    assert second.max_price == Decimal(2500)


def test_a_new_category_starts_a_new_search():
    villa = SearchFilters(category="villas", listing_type="rent", location="Lusail")
    merged, notes = merge(PHONE, villa, CATALOG)
    assert merged == villa and notes == ["new category: villas"]


def test_brand_switch_drops_models_of_other_brands():
    merged, notes = merge(PHONE, SearchFilters(brands=["Samsung"]), CATALOG)
    assert merged.brands == ["Samsung"] and merged.models == []
    assert merged.conditions == PHONE.conditions  # "used" survives the switch
    assert "models of other brands dropped" in notes


def test_new_models_drop_a_brand_they_do_not_belong_to():
    merged, _ = merge(PHONE, SearchFilters(models=["Galaxy S24 Ultra"]), CATALOG)
    assert merged.models == ["Galaxy S24 Ultra"] and merged.brands == []


def test_attributes_merge_by_key_and_keywords_combine():
    prev = PHONE.model_copy(update={"attributes": {"storage_gb": {"eq": 256}}})
    delta = SearchFilters(attributes={"storage_gb": {"eq": 512}}, keywords=["512GB"])
    merged, _ = merge(prev, delta, CATALOG)
    assert merged.attributes["storage_gb"].eq == 512
    assert merged.keywords == ["Pro", "512GB"]


def test_rent_price_without_period_becomes_monthly():
    prev = SearchFilters(category="villas", listing_type="rent")
    merged, _ = merge(prev, SearchFilters(max_price=Decimal(25000)), CATALOG)
    assert merged.price_period == "month"


def test_cheaper_sets_a_ceiling_just_below_the_median():
    merged, notes = merge(PHONE, SearchFilters(), CATALOG, cheaper_than=Decimal("2400"))
    assert merged.max_price == Decimal("2399.999") and merged.currency == "QAR"
    assert merged.price_period is None and notes[-1] == "cheaper: below median 2400 QAR"
    rent = SearchFilters(category="apartments", listing_type="rent")
    merged, _ = merge(rent, SearchFilters(), CATALOG, cheaper_than=Decimal("9000"))
    assert merged.price_period == "month"


def test_an_explicit_price_wins_over_cheaper():
    merged, notes = merge(PHONE, SearchFilters(max_price=Decimal(1500)), CATALOG, Decimal(2400))
    assert merged.max_price == Decimal(1500)
    assert notes[-1] == "cheaper: explicit price used instead of the median"


def test_first_message_and_failed_extraction():
    assert merge(None, PHONE, CATALOG) == (PHONE, ["new search"])
    assert merge(PHONE, None, CATALOG)[0] == PHONE  # extraction failed: keep the state


class MedianConn:
    def __init__(self, value):
        self.value, self.sql, self.params = value, None, None

    async def fetchval(self, sql, *params):
        self.sql, self.params = sql, params
        return self.value


async def test_median_price_uses_comparable_prices_under_the_previous_filters():
    conn = MedianConn(2350.5)
    assert await median_price(conn, PHONE, RATES) == Decimal("2350.5")
    assert "percentile_cont(0.5)" in conn.sql and "price_qar / 12" in conn.sql
    assert "category = $1" in conn.sql and conn.params[0] == "phones"


# --- session ---------------------------------------------------------------------------------


def test_history_is_capped_and_query_text_accumulates():
    s = Session("s")
    for i in range(30):
        s.remember("user", f"m{i}")
    assert len(s.history) == 20 and s.history[-1]["text"] == "m29"
    assert (
        combine_query("used iPhone 15 Pro Max", "under 2000") == "used iPhone 15 Pro Max under 2000"
    )
    long = combine_query("a" * 400, "b" * 400)
    assert len(long) <= 501 and long.startswith("a") and long.endswith("b")


# --- a multi-turn chat with fakes ------------------------------------------------------------


class MemoryStore:
    def __init__(self):
        self.rows: dict[str, Session] = {}

    async def load(self, conn, session_id):
        return self.rows.get(session_id) or Session(session_id)

    async def save(self, conn, session):
        self.rows[session.session_id] = session


class Conn:
    async def fetch(self, sql, ids):
        return []

    async def fetchrow(self, sql, *params):
        return Zeros()  # relaxation counts for an empty result

    async def fetchval(self, sql, *params):
        return 2400.0  # median for "cheaper"


class Zeros(dict):
    def __missing__(self, key):
        return 0


class Pool:
    @asynccontextmanager
    async def acquire(self):
        yield Conn()


class Embedder:
    model = "fake"

    async def embed_query(self, text):
        return QueryVector("[1]", True, text)


class Understander:
    """Context-free deltas per message, like the real cached extraction."""

    catalog = CATALOG
    DELTAS = {
        "used iPhone 15 Pro Max": PHONE,
        "under 2000 riyals": SearchFilters(max_price=Decimal(2000)),
        "what about Samsung?": SearchFilters(brands=["Samsung"]),
        "cheaper ones": SearchFilters(),
        "show me villas in Lusail": SearchFilters(category="villas", location="Lusail"),
    }

    async def lookup(self, conn, query):
        f = self.DELTAS[query]
        return Understanding(f, None, True, 1.0)

    def with_context(self, understood, query, category):
        return understood


class Search:
    def __init__(self):
        self.pool, self.embedder, self.understanding = Pool(), Embedder(), Understander()
        self.calls, self.nearby = [], []  # main searches; "closest matches" searches

    async def search(self, request):
        calls = self.nearby if request.limit == NEARBY_LIMIT else self.calls
        calls.append((request.query, dump(request.filters)))
        return SearchResponse(query=request.query, results=[])


async def run_turns(service, session_id, messages):
    for m in messages:
        async for _ in service.events(m, session_id):
            pass


async def test_a_conversation_merges_turn_by_turn_and_resets():
    search, store = Search(), MemoryStore()
    service = ChatService(search, None, RATES, store)
    await run_turns(service, "s1", ["used iPhone 15 Pro Max", "under 2000 riyals",
                                    "what about Samsung?", "cheaper ones"])  # fmt: skip
    queries = [q for q, _ in search.calls]
    states = [f for _, f in search.calls]
    assert states[1] == {**dump(PHONE), "max_price": "2000"}
    assert states[2]["brands"] == ["Samsung"] and "models" not in states[2]
    assert states[3]["max_price"] == "2399.999"  # below the median of the previous search
    assert queries[3] == "used iPhone 15 Pro Max under 2000 riyals what about Samsung? cheaper ones"
    assert store.rows["s1"].turns == 4

    await run_turns(service, "s1", ["start over"])
    assert store.rows["s1"].filters is None and store.rows["s1"].search_query == ""
    assert len(search.calls) == 4  # "start over" alone makes no search

    await run_turns(service, "s1", ["show me villas in Lusail"])
    assert search.calls[-1] == ("show me villas in Lusail",
                                {"category": "villas", "location": "Lusail"})  # fmt: skip


async def test_sessions_are_independent():
    search, store = Search(), MemoryStore()
    service = ChatService(search, None, RATES, store)
    await run_turns(service, "a", ["used iPhone 15 Pro Max"])
    await run_turns(service, "b", ["under 2000 riyals"])
    assert search.calls[1] == ("under 2000 riyals", {"max_price": "2000"})  # no phone context


async def test_edited_filter_tokens_replace_the_state_without_extraction():
    search, store = Search(), MemoryStore()
    service = ChatService(search, None, RATES, store)
    await run_turns(service, "e", ["used iPhone 15 Pro Max", "under 2000 riyals"])
    edited = SearchFilters(category="phones", models=["iPhone 15 Pro Max"])  # removed 2 tokens
    async for _ in service.events("Removed: Used, Under 2,000 QAR", "e", edited):
        pass
    query, filters = search.calls[-1]
    assert filters == {"category": "phones", "models": ["iPhone 15 Pro Max"]}
    # Retrieval text is rebuilt from what is left, so removed values stop steering ranking.
    assert query == "iPhone 15 Pro Max phones"
    assert store.rows["e"].filters == edited and store.rows["e"].turns == 3


def test_removing_the_model_drops_it_from_retrieval_text_and_keywords():
    before = SearchFilters(
        category="phones",
        brands=["Apple"],
        models=["iPhone 17"],
        conditions=["like_new", "good"],
        keywords=["iPhone 17", "great"],
    )
    edited = before.model_copy(update={"models": []})
    cleaned = drop_removed_keywords(before, edited)
    assert cleaned.keywords == ["great"]
    assert describe(cleaned) == "like new or good Apple phones"
    assert "17" not in describe(cleaned)


def test_describe_covers_rentals_and_attributes():
    f = SearchFilters(
        category="apartments",
        listing_type="rent",
        location="Lusail",
        attributes={
            "bedrooms": {"eq": 2},
            "furnished": {"eq": "furnished"},
            "private_pool": {"eq": True},
        },
    )
    assert describe(f) == "apartments for rent in Lusail 2 bedrooms furnished private pool"


async def test_no_match_sends_relaxations_first_then_the_closest_listings():
    search, store = Search(), MemoryStore()
    service = ChatService(search, None, RATES, store)
    names = [e.name async for e in service.events("used iPhone 15 Pro Max", "n")]
    assert names[:3] == ["filters", "listings", "no_match"]
    assert names.index("nearby") > names.index("token") and names[-1] == "done"
    # The nearby search keeps the person's words and only the kind of item.
    query, filters = search.nearby[-1]
    assert query == search.calls[-1][0] and filters == {"category": "phones"}
