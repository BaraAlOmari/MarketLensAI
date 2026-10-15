"""SearchService orchestration with fake dependencies: cache paths, filters, and fallback."""

from contextlib import asynccontextmanager

import pytest

import app.retrieval.service as service_module
from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.models.filters import QueryParse, SearchFilters, parse_to_filters
from app.models.search import SearchRequest
from app.providers.query_cache import QueryVector
from app.retrieval.hybrid import HybridResult
from app.retrieval.service import SearchService
from app.retrieval.understanding import Understanding


class FakePool:
    def __init__(self) -> None:
        self.acquired = 0

    @asynccontextmanager
    async def acquire(self):
        self.acquired += 1
        yield object()


class FakeEmbedder:
    model = "fake-embed"

    def __init__(self, cached: bool) -> None:
        self.cached = cached

    async def lookup(self, conn, text):
        return QueryVector("[1,0]", True, text) if self.cached else None

    async def embed_and_store(self, text):
        return QueryVector("[1,0]", False, text)


class FakeUnderstanding:
    model = "fake-lite"

    def __init__(self, parse: QueryParse | None = None, cached: bool = False, error=None):
        self.parse, self.cached, self.error = parse, cached, error
        self.calls = 0

    def _result(self, cached: bool) -> Understanding:
        if self.error:
            return Understanding(None, None, False, 5.0, error=self.error)
        return Understanding(parse_to_filters(self.parse, RATES), self.parse, cached, 5.0)

    async def lookup(self, conn, query):
        return self._result(True) if self.cached and not self.error else None

    async def extract_and_store(self, query):
        self.calls += 1
        return self._result(False)


@pytest.fixture
def searches(monkeypatch):
    """Capture what retrieval was asked to do instead of touching a database."""
    seen = []

    async def fake_vector_search(conn, literal, model, limit, clauses=(), params=()):
        seen.append({"mode": "vector", "clauses": list(clauses), "params": list(params)})
        return []

    async def fake_hybrid_search(conn, literal, model, query, depth, clauses=(), params=(), k=60):
        seen.append({"mode": "hybrid", "clauses": list(clauses), "params": list(params),
                     "query": query, "depth": depth, "k": k})  # fmt: skip
        return HybridResult({}, [], [], [])

    monkeypatch.setattr(service_module, "vector_search", fake_vector_search)
    monkeypatch.setattr(service_module.hybrid, "hybrid_search", fake_hybrid_search)
    return seen


PARSE = QueryParse(category="phones", price={"comparator": "under", "amount": 1000})


async def test_extracted_filters_are_applied(searches):
    svc = SearchService(FakePool(), FakeEmbedder(cached=False), FakeUnderstanding(PARSE), RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", debug=True))
    assert resp.extracted_filters == {"category": "phones", "max_price": "1000"}
    assert any("price_qar <=" in c for c in searches[0]["clauses"])
    assert resp.debug.retrieval == "hybrid+filters" and resp.debug.filters_source == "llm"


async def test_failed_extraction_falls_back_to_unfiltered_search(searches):
    understanding = FakeUnderstanding(error="extraction call failed: TimeoutError")
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), understanding, RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", debug=True))
    assert searches[0]["clauses"] == []  # searched without filters
    assert resp.extracted_filters is None
    assert resp.debug.retrieval == "hybrid"
    assert resp.debug.extraction.error.startswith("extraction call failed")


async def test_everything_cached_uses_one_connection_and_no_llm_call(searches):
    pool, understanding = FakePool(), FakeUnderstanding(PARSE, cached=True)
    svc = SearchService(pool, FakeEmbedder(cached=True), understanding, RATES)
    await svc.search(SearchRequest(query="phone under 1000"))
    assert pool.acquired == 1 and understanding.calls == 0


async def test_explicit_filters_skip_the_llm(searches):
    understanding = FakeUnderstanding(PARSE)
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), understanding, RATES)
    request = SearchRequest(query="sofa", filters=SearchFilters(category="furniture"))
    resp = await svc.search(request)
    assert understanding.calls == 0
    assert resp.extracted_filters == {"category": "furniture"}


async def test_extract_false_reproduces_the_baseline(searches):
    understanding = FakeUnderstanding(PARSE)
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), understanding, RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", extract=False, debug=True))
    assert understanding.calls == 0 and searches[0]["clauses"] == []
    assert resp.debug.filters_source == "none"


async def test_hybrid_is_the_default_and_gets_the_same_filters(searches):
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), FakeUnderstanding(PARSE), RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", debug=True))
    hybrid_call = searches[0]
    # Default keyword source is the LLM's keywords: none here, so no full-text side.
    assert hybrid_call["mode"] == "hybrid" and hybrid_call["query"] == ""
    assert hybrid_call["depth"] == 50 and hybrid_call["k"] == 60
    # Filter parameters are numbered after the hybrid query's own four ($1..$4).
    assert any("price_qar <= $" in c for c in hybrid_call["clauses"])
    assert all("$4" not in c for c in hybrid_call["clauses"])
    assert resp.debug.retrieval == "hybrid+filters"

    resp = await svc.search(SearchRequest(query="phone under 1000", retrieval="vector", debug=True))
    vector_call = searches[1]
    assert vector_call["mode"] == "vector"
    assert len(vector_call["clauses"]) == len(hybrid_call["clauses"])  # same filters, both modes
    assert resp.debug.retrieval == "vector+filters"


async def test_keyword_side_uses_llm_keywords_or_the_raw_query(searches):
    parse = QueryParse(category="phones", keywords=["512GB", "S24"])
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), FakeUnderstanding(parse), RATES)
    await svc.search(SearchRequest(query="used galaxy s24 512GB"))
    assert searches[-1]["query"] == "512GB S24"
    svc.hybrid_keywords = "query"
    await svc.search(SearchRequest(query="used galaxy s24 512GB"))
    assert searches[-1]["query"] == "used galaxy s24 512GB"
