"""Stage 7: grounded answers. The acceptance rule is that no response ever contains a price or
link that did not come from the database, and that hallucinated listing ids are dropped."""

import json
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.answers.chat import ChatService, chunks, sse
from app.answers.grounding import (
    clean_summary,
    ground,
    has_link,
    has_price,
    template_answer,
    validate_citations,
)
from app.answers.relax import Relaxation, no_match_message, relax_counts, relaxed_variants
from app.api.chat import get_chat_service
from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.config import Settings
from app.main import create_app
from app.models.filters import SearchFilters
from app.models.search import ListingResult, SearchResponse
from app.providers.gemini import JsonResult
from app.providers.llm import (
    Answer,
    AnswerError,
    GeminiLLMProvider,
    answer_candidates,
    reply_language,
)
from app.providers.query_cache import QueryVector
from tests.test_filters import CATALOG

ROW = {
    "external_id": "x", "title": "iPhone 15 Pro Max 256GB", "description": "clean, box " * 30,
    "category": "phones", "brand": "Apple", "model": "iPhone 15 Pro Max",
    "currency": "QAR", "condition": "like_new", "listing_type": "sale",
    "price_period": "total", "attributes": '{"storage_gb": 256}', "location": "Lusail",
    "language": "en", "image_url": None,
}  # fmt: skip


def row(i: int, price: str) -> dict:
    return {**ROW, "id": i, "external_id": f"x{i}", "price": Decimal(price),
            "price_qar": Decimal(price)}  # fmt: skip


def listing(i: int, price: str = "2000") -> ListingResult:
    data = row(i, price)
    data["attributes"] = json.loads(data["attributes"])
    return ListingResult(**data, score=0.5)


# --- grounding ---------------------------------------------------------------------------


def test_hallucinated_ids_are_dropped():
    # The model was shown listings 101, 102, 103 as numbers 1..3.
    kept, dropped = validate_citations([2, 7, 0, -1, 2, 3, 1], [101, 102, 103])
    assert kept == [102, 103, 101]
    assert dropped == [7, 0, -1, 2]  # out of range, or repeated


def test_at_most_three_citations():
    kept, _ = validate_citations([1, 2, 3, 4], [1, 2, 3, 4])
    assert kept == [1, 2, 3]


@pytest.mark.parametrize(
    "text",
    ["It is only 3,500 QAR.", "Asking 900 riyals.", "السعر 900 ريال.", "Just $899 today.",
     "Priced at 1200, negotiable.", "Under 40k.", "بسعر ١٥٠٠."],
)  # fmt: skip
def test_prices_are_detected(text):
    assert has_price(text)


@pytest.mark.parametrize(
    "text",
    ["The 512GB one is like new.", "A 2020 Land Cruiser with 45,000 km.", "5 bedrooms.",
     "It has a 4K screen.", "Two are in Lusail."],
)  # fmt: skip
def test_specs_are_not_mistaken_for_prices(text):
    assert not has_price(text)


@pytest.mark.parametrize(
    "text",
    ["See https://olx.qa/item/1", "www.example.com", "Call 5512 3456", "+974 3344-5566",
     "wa.me/97455123456", "mail seller@x.qa"],
)  # fmt: skip
def test_links_and_contacts_are_detected(text):
    assert has_link(text)


def test_sentences_with_prices_or_links_are_removed():
    text, removed = clean_summary(
        "I found 4 phones. The best is 2,100 QAR! Two come with the box. See wa.me/9745511."
    )
    assert text == "I found 4 phones. Two come with the box." and removed == 2


def test_nothing_left_falls_back_to_a_template():
    g = ground("used iphone", "Only 900 QAR. Call 5512 3456.", [1], [11, 12])
    assert g.used_template and g.summary == template_answer("used iphone", 2)
    assert not has_price(g.summary) and g.cited_ids == [11]
    assert "بطاقات" in template_answer("ايفون مستعمل", 3)


# --- answer prompt -----------------------------------------------------------------------


def test_answer_model_never_sees_listing_prices():
    items = [listing(1, "2399"), listing(2, "1875"), listing(3, "3150")]
    text = "\n".join(answer_candidates(items))
    assert "2399" not in text and "1875" not in text and "3150" not in text
    assert "[2] " in text and "price rank 1 of 3 (1 = cheapest)" in text.split("\n")[1]


def test_reply_language_is_decided_in_code():
    assert reply_language("شقة غرفتين للإيجار في لوسيل") == "Arabic"
    assert reply_language("used iPhone 15 Pro Max") == "English"
    assert reply_language("iPhone 14 نظيف أقل من 1500 ريال") == "Arabic"


class FakeLLMClient:
    model = "fake-lite"
    api = "generate_content"

    def __init__(self, text="{}", error=None):
        self.text, self.error, self.prompts = text, error, []

    async def generate_json(self, *, system, prompt, schema, thinking_level="low"):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return JsonResult(self.text, 500, 60, 0)


def provider(client) -> GeminiLLMProvider:
    return GeminiLLMProvider(client, CATALOG, ["QAR", "USD"], rpm_limit=1000)


async def test_generate_answer_parses_and_keeps_only_integer_numbers():
    client = FakeLLMClient(json.dumps({"summary": " Two good ones. ", "recommended": [2, "x", 1]}))
    answer = await provider(client).generate_answer("phone", [listing(1), listing(2)])
    assert answer.summary == "Two good ones." and answer.recommended == [2, 1]
    assert "Reply language: English" in client.prompts[0]


@pytest.mark.parametrize(
    "client",
    [FakeLLMClient(error=TimeoutError()), FakeLLMClient("not json"),
     FakeLLMClient('{"summary": "  "}'), FakeLLMClient('{"recommended": [1]}')],
)  # fmt: skip
async def test_generate_answer_failures_raise_answer_error(client):
    with pytest.raises(AnswerError):
        await provider(client).generate_answer("phone", [listing(1)])


# --- no matches ----------------------------------------------------------------------------


def test_relaxed_variants_drop_one_constraint_each_and_never_the_category():
    f = SearchFilters(category="villas", max_price=Decimal(5), location="Lusail",
                      attributes={"bedrooms": {"eq": 3}})  # fmt: skip
    names = [n for n, _ in relaxed_variants(f)]
    assert names == ["price", "location", "attr:bedrooms"]
    assert all(v.category == "villas" for _, v in relaxed_variants(f))


class CountConn:
    def __init__(self):
        self.sql, self.params = None, None

    async def fetchrow(self, sql, *params):
        self.sql, self.params = sql, params
        return {"v0": 0, "v1": 4}


async def test_relax_counts_use_one_query():
    conn = CountConn()
    f = SearchFilters(category="apartments", min_price=Decimal(3000000), location="The Pearl")
    out = await relax_counts(conn, f, RATES)
    assert out == [Relaxation("price", 0), Relaxation("location", 4)]
    assert conn.sql.count("count(*) filter") == 2 and "$1" in conn.sql and "$3" in conn.sql


def test_no_match_message_is_built_from_counts():
    rel = [Relaxation("price", 0), Relaxation("location", 4), Relaxation("attr:bedrooms", 1)]
    en = no_match_message("penthouse in The Pearl", rel)
    assert en == ("Nothing matches all of your filters. Without the location there are 4; "
                  "without the bedroom count there is 1.")  # fmt: skip
    assert "بدون الموقع يوجد 4" in no_match_message("شقة في اللؤلؤة", rel)
    assert "Try relaxing" in no_match_message("x", [Relaxation("price", 0)])


# --- the chat stream -----------------------------------------------------------------------


class FakeConn:
    """Serves listing rows (the 'database') and misses the answer cache."""

    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, sql, ids):
        return [self.rows[i] for i in ids if i in self.rows]

    async def fetchrow(self, sql, *params):
        return None

    async def execute(self, sql, *params):
        return None


class FakePool:
    def __init__(self, rows):
        self.rows = rows

    @asynccontextmanager
    async def acquire(self):
        yield FakeConn(self.rows)


class FakeEmbedder:
    model = "fake-embed"

    async def embed_query(self, text):
        return QueryVector("[1]", True, text)


class FakeSearch:
    def __init__(self, pool, results):
        self.pool, self.embedder, self.understanding = pool, FakeEmbedder(), None
        self.results = results

    async def search(self, request):
        return SearchResponse(query=request.query, results=self.results)


class LyingAnswers:
    """An answer model that does everything wrong at once."""

    def __init__(self):
        self.llm = type("L", (), {"model": "fake-lite"})()
        self.languages = []

    async def lookup(self, conn, query, listings, language=None):
        return None

    async def generate_and_store(self, query, listings, language=None):
        self.languages.append(language)
        return Answer(
            "I found 2 iPhones. The first is only 999 QAR! Both have the box. "
            "Message 5512 3456 or visit https://scam.example.com.",
            recommended=[9, 2, 2],
        )


def chat_events(service: ChatService, message: str) -> list[tuple[str, dict]]:
    app = create_app(Settings(_env_file=None, database_url=None))
    app.dependency_overrides[get_chat_service] = lambda: service
    with TestClient(app) as client:
        resp = client.post("/api/chat", json={"session_id": "s1", "message": message})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_chat_stream_never_leaks_invented_prices_links_or_ids():
    # The "database" has the real prices; search returned stale copies of the same ids.
    db = {1: row(1, "2100.00"), 2: row(2, "2250.00")}  # numeric(14, 2), as Postgres returns it
    stale = [listing(1, "1"), listing(2, "1")]
    service = ChatService(FakeSearch(FakePool(db), stale), LyingAnswers(), RATES)
    events = chat_events(service, "used iPhone 15 Pro Max")

    assert [n for n, _ in events][:2] == ["filters", "listings"]
    assert events[-1][0] == "done"
    cards = events[1][1]["listings"]
    assert [c["price"] for c in cards] == ["2100.00", "2250.00"]  # from the DB rows

    text = "".join(d["text"] for n, d in events if n == "token")
    assert text == "I found 2 iPhones. Both have the box."
    assert not has_price(text) and not has_link(text)

    done = events[-1][1]
    assert done["cited_ids"] == [2]  # 9 was never shown; the repeated 2 counts once
    assert done["grounding"] == {"dropped_ids": [9, 2], "removed_sentences": 2,
                                 "used_template": False}  # fmt: skip


def test_chat_with_no_results_gives_a_template_and_no_cards():
    service = ChatService(FakeSearch(FakePool({}), []), LyingAnswers(), RATES)
    events = chat_events(service, "unicorn")
    assert events[1] == ("listings", {"listings": []})
    text = "".join(d["text"] for n, d in events if n == "token")
    assert text.startswith("Nothing matches") and events[-1][1]["no_match"] is True


def test_chat_rejects_bad_requests():
    app = create_app(Settings(_env_file=None, database_url=None))
    with TestClient(app) as client:
        assert client.post("/api/chat", json={"message": "x"}).status_code == 422
        assert client.post("/api/chat", json={"session_id": "s", "message": " "}).status_code == 422
        resp = client.post("/api/chat", json={"session_id": "s", "message": "phone"})
    # Not configured: the stream reports it instead of failing.
    assert "event: error" in resp.text and "event: done" in resp.text


def test_sse_format_and_chunks():
    assert sse(type("E", (), {"name": "token", "data": {"text": "hi"}})()) == (
        'event: token\ndata: {"text": "hi"}\n\n'
    )
    assert "".join(chunks("one two three four five six")) == "one two three four five six"


def test_reply_language_follows_the_latest_message():
    # Found in the first multi-turn run: "أرخص" after an English conversation got English,
    # because the language came from the accumulated query text.
    answers = LyingAnswers()
    service = ChatService(
        FakeSearch(FakePool({1: row(1, "2100.00")}), [listing(1)]), answers, RATES
    )
    chat_events(service, "Galaxy S24 Ultra")
    chat_events(service, "أرخص")
    assert answers.languages == ["English", "Arabic"]
