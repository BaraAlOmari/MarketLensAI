"""SearchService orchestration with fake dependencies: cache paths, filters, and fallback."""

from contextlib import asynccontextmanager

import pytest

import app.retrieval.service as service_module
from app.config import DEFAULT_FX_RATES_TO_QAR as RATES
from app.models.filters import QueryParse, SearchFilters, parse_to_filters
from app.models.search import SearchRequest
from app.providers.query_cache import QueryVector
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
    """Capture what vector_search was asked to do instead of touching a database."""
    seen = []

    async def fake_vector_search(conn, literal, model, limit, clauses=(), params=()):
        seen.append({"clauses": list(clauses), "params": list(params), "limit": limit})
        return []

    monkeypatch.setattr(service_module, "vector_search", fake_vector_search)
    return seen


PARSE = QueryParse(category="phones", price={"comparator": "under", "amount": 1000})


async def test_extracted_filters_are_applied(searches):
    svc = SearchService(FakePool(), FakeEmbedder(cached=False), FakeUnderstanding(PARSE), RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", debug=True))
    assert resp.extracted_filters == {"category": "phones", "max_price": "1000"}
    assert any("price_qar <=" in c for c in searches[0]["clauses"])
    assert resp.debug.retrieval == "vector+filters" and resp.debug.filters_source == "llm"


async def test_failed_extraction_falls_back_to_unfiltered_search(searches):
    understanding = FakeUnderstanding(error="extraction call failed: TimeoutError")
    svc = SearchService(FakePool(), FakeEmbedder(cached=True), understanding, RATES)
    resp = await svc.search(SearchRequest(query="phone under 1000", debug=True))
    assert searches[0]["clauses"] == []  # searched without filters
    assert resp.extracted_filters is None
    assert resp.debug.retrieval == "vector"
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
