"""Stage 6 reranking: ranking validation, the Gemini wrapper, and fallbacks in search."""

import json
from decimal import Decimal

import pytest

import app.retrieval.service as service_module
from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.models.search import ListingResult, SearchRequest
from app.providers.gemini import JsonResult
from app.providers.ratelimit import SlidingWindowLimiter
from app.providers.rerank import (
    GeminiListwiseReranker,
    RerankError,
    apply_ranking,
    build_prompt,
    candidate_text,
)
from app.retrieval.reranking import RerankOutcome, _with_rank
from app.retrieval.service import SearchService
from tests.test_search_service import FakeEmbedder, FakePool


def listing(i: int, **over) -> ListingResult:
    base = {
        "id": i, "external_id": f"x{i}", "title": f"Listing {i}", "description": "nice " * 60,
        "category": "laptops", "brand": "Apple", "model": "MacBook Air 13 M4",
        "price": Decimal("3500"), "currency": "QAR", "price_qar": Decimal("3500"),
        "condition": "like_new", "listing_type": "sale", "price_period": "total",
        "attributes": {"ram_gb": 16, "storage_gb": 512}, "location": "Lusail", "language": "en",
        "image_url": None, "score": 0.5,
    }  # fmt: skip
    return ListingResult(**{**base, **over})


# --- apply_ranking -------------------------------------------------------------------


def test_ranking_keeps_valid_numbers_then_the_rest_in_retrieval_order():
    order, ranked, invalid = apply_ranking(5, [3, 1], top_n=10)
    assert order == [2, 0, 1, 3, 4] and (ranked, invalid) == (2, 0)


def test_invalid_repeated_and_out_of_range_numbers_are_dropped():
    order, ranked, invalid = apply_ranking(4, [2, 2, 0, 9, -1, "3", 4], top_n=10)
    assert order == [1, 3, 0, 2] and (ranked, invalid) == (2, 5)


def test_top_n_caps_what_the_reranker_decides():
    order, ranked, _ = apply_ranking(5, [5, 4, 3, 2, 1], top_n=2)
    assert order == [4, 3, 0, 1, 2] and ranked == 2


def test_every_candidate_appears_exactly_once():
    order, _, _ = apply_ranking(50, list(range(50, 0, -3)), top_n=10)
    assert sorted(order) == list(range(50))


# --- prompt --------------------------------------------------------------------------


def test_candidate_text_has_title_facts_and_a_short_description():
    text = candidate_text(listing(1))
    assert text.startswith("Listing 1 | laptops | Apple | MacBook Air 13 M4 | 3,500 QAR")
    assert "ram gb: 16" in text and "like new" in text
    assert len(text.split(" | ")[-1]) == 160  # description cut to 160 characters


def test_rent_price_shows_the_period():
    rent = listing(2, category="apartments", listing_type="rent", price_period="month",
                   condition=None, price=Decimal("8000"))  # fmt: skip
    assert "8,000 QAR per month" in candidate_text(rent)


def test_prompt_numbers_candidates_from_one():
    prompt = build_prompt("light laptop", ["a", "b"])
    assert prompt.endswith("Candidates:\n[1] a\n[2] b") and prompt.startswith("Query: light laptop")


# --- Gemini wrapper ------------------------------------------------------------------


class FakeClient:
    model = "fake-lite"
    api = "generate_content"

    def __init__(self, text="{}", error=None):
        self.text, self.error, self.calls = text, error, []

    async def generate_json(self, *, system, prompt, schema, thinking_level="low"):
        self.calls.append({"system": system, "prompt": prompt})
        if self.error:
            raise self.error
        return JsonResult(self.text, 900, 20, 0)


def reranker(client) -> GeminiListwiseReranker:
    return GeminiListwiseReranker(client, limiter=SlidingWindowLimiter(1000))


async def test_reranker_returns_a_full_order_and_tokens():
    client = FakeClient(json.dumps({"ranking": [3, 1]}))
    out = await reranker(client).rerank("q", [listing(i) for i in (10, 11, 12)], top_n=10)
    assert out.order == [2, 0, 1] and out.ranked == 2
    assert (out.input_tokens, out.output_tokens) == (900, 20)
    assert "at most 10" in client.calls[0]["system"]


@pytest.mark.parametrize(
    "client",
    [FakeClient(error=TimeoutError()), FakeClient("not json"), FakeClient('{"ranking": []}'),
     FakeClient('{"ranking": [7, 8]}'), FakeClient('{"other": 1}')],
)  # fmt: skip
async def test_reranker_failures_raise_rerank_error(client):
    with pytest.raises(RerankError):
        await reranker(client).rerank("q", [listing(1), listing(2)], top_n=10)


def test_with_rank_records_the_new_position():
    items = [listing(1), listing(2, ranks={"vector": 1})]
    out = _with_rank(items, [1, 0])
    assert [r.id for r in out] == [2, 1]
    assert out[0].ranks == {"vector": 1, "rerank": 1} and out[1].ranks == {"rerank": 2}


# --- in search -----------------------------------------------------------------------


class FakeReranker:
    model = "fake-lite"

    def __init__(self, cached_order=None, error=None):
        self.cached_order, self.error = cached_order, error
        self.calls = []

    async def lookup(self, conn, query, candidates, top_n):
        if self.cached_order is None:
            return None
        return RerankOutcome(_with_rank(candidates, self.cached_order), True, 1.0, ranked=2)

    async def rerank_and_store(self, query, candidates, top_n):
        self.calls.append({"n": len(candidates), "top_n": top_n})
        if self.error:
            return RerankOutcome(list(candidates), False, 5.0, error=self.error)
        order = list(range(len(candidates)))[::-1]  # reverse, to make the effect visible
        return RerankOutcome(_with_rank(candidates, order), False, 5.0, ranked=len(order))


@pytest.fixture
def pool_of(monkeypatch):
    """Retrieval returns `n` listings in id order; records the requested depth."""
    asked = {}

    def install(n: int):
        async def fake_retrieve(self, conn, mode, query, vector, filters, limit):
            asked["depth"] = limit
            return [listing(i) for i in range(1, min(n, limit) + 1)], {"vector": n}

        monkeypatch.setattr(service_module.SearchService, "_retrieve", fake_retrieve)
        return asked

    return install


def service(rr) -> SearchService:
    return SearchService(FakePool(), FakeEmbedder(cached=True), None, RATES, reranker=rr)


async def test_rerank_reorders_a_deeper_pool_and_cuts_the_page(pool_of):
    asked, rr = pool_of(30), FakeReranker()
    resp = await service(rr).search(SearchRequest(query="laptop", limit=5, debug=True))
    assert asked["depth"] == 50  # deeper pool than the page
    assert [r.id for r in resp.results] == [30, 29, 28, 27, 26]
    assert resp.results[0].ranks["rerank"] == 1
    assert rr.calls == [{"n": 30, "top_n": 10}]
    assert resp.debug.retrieval.endswith("+rerank") and resp.debug.rerank.candidates == 30


async def test_cached_rerank_makes_no_call(pool_of):
    pool_of(3)
    rr = FakeReranker(cached_order=[2, 0, 1])
    resp = await service(rr).search(SearchRequest(query="laptop", debug=True))
    assert [r.id for r in resp.results] == [3, 1, 2] and rr.calls == []
    assert resp.debug.rerank.cached is True


async def test_failed_rerank_keeps_the_retrieval_order(pool_of):
    pool_of(4)
    rr = FakeReranker(error="rerank call failed: TimeoutError")
    resp = await service(rr).search(SearchRequest(query="laptop", debug=True))
    assert [r.id for r in resp.results] == [1, 2, 3, 4]
    assert resp.debug.rerank.error.startswith("rerank call failed")


async def test_rerank_false_and_single_candidates_skip_the_reranker(pool_of):
    asked, rr = pool_of(20), FakeReranker()
    resp = await service(rr).search(SearchRequest(query="laptop", rerank=False, debug=True))
    assert rr.calls == [] and asked["depth"] == 10 and resp.debug.rerank is None
    pool_of(1)
    await service(rr).search(SearchRequest(query="laptop"))
    assert rr.calls == []  # nothing to order
