from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.search import get_search_service
from app.config import Settings
from app.main import create_app
from app.models.search import ListingResult, SearchDebug, SearchResponse
from app.providers.query_cache import cache_key, normalize_query
from app.providers.retry import QuotaExhaustedError
from app.retrieval.service import to_result
from app.retrieval.vector import ef_search_for

LISTING = {
    "id": 7,
    "external_id": "syn-qa-00007",
    "title": "iPhone 15 Pro 256GB",
    "description": "clean, w/ box",
    "category": "phones",
    "brand": "Apple",
    "model": "iPhone 15 Pro",
    "price": Decimal("2800.00"),
    "currency": "QAR",
    "price_qar": Decimal("2800.00"),
    "condition": "like_new",
    "listing_type": "sale",
    "price_period": "total",
    "attributes": '{"storage_gb": 256}',
    "location": "Lusail",
    "language": "en",
    "image_url": None,
    "score": 0.81,
}


class FakeService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests = []

    async def search(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        debug = SearchDebug(
            retrieval="vector",
            embedding_model="fake",
            embedding_cached=True,
            filters_source="none",
            timings_ms={},
        )
        return SearchResponse(
            query=request.query,
            results=[to_result(LISTING)],
            debug=debug if request.debug else None,
        )


def client_with(service) -> TestClient:
    app = create_app(Settings(_env_file=None, database_url=None))
    app.dependency_overrides[get_search_service] = lambda: service
    return TestClient(app)


def test_search_returns_results_in_contract_shape():
    service = FakeService()
    with client_with(service) as client:
        resp = client.post("/api/search", json={"query": "  used iPhone 15 Pro ", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"query", "extracted_filters", "results", "debug"}
    assert body["query"] == "used iPhone 15 Pro"
    assert body["extracted_filters"] is None and body["debug"] is None
    result = body["results"][0]
    assert result["attributes"] == {"storage_gb": 256}
    assert result["price"] == "2800.00" and result["condition"] == "like_new"
    assert service.requests[0].limit == 5


def test_debug_is_included_on_request():
    with client_with(FakeService()) as client:
        body = client.post("/api/search", json={"query": "sofa", "debug": True}).json()
    assert body["debug"]["retrieval"] == "vector"


def test_rejects_blank_query_bad_limit_and_unknown_fields():
    with client_with(FakeService()) as client:
        assert client.post("/api/search", json={"query": "   "}).status_code == 422
        assert client.post("/api/search", json={"query": "x", "limit": 0}).status_code == 422
        assert client.post("/api/search", json={"query": "x", "limit": 51}).status_code == 422
        resp = client.post("/api/search", json={"query": "x", "sort": "price"})
        assert resp.status_code == 422  # unknown fields are never silently ignored


def test_explicit_filters_are_validated():
    service = FakeService()
    with client_with(service) as client:
        ok = client.post(
            "/api/search",
            json={"query": "phone", "filters": {"category": "phones", "max_price": 3000,
                                                "attributes": {"storage_gb": {"eq": 256}}}},
        )  # fmt: skip
        assert ok.status_code == 200
        assert service.requests[0].filters.attributes["storage_gb"].eq == 256
        for bad in (
            {"max_prise": 3000},  # typo'd field
            {"attributes": {"seller_name": {"eq": "x"}}},  # not a filterable attribute
            {"attributes": {"year": {}}},  # no operator
            {"attributes": {"year": {"eq": 2020, "min": 2019}}},  # conflicting operators
            {"conditions": ["mint"]},
        ):
            resp = client.post("/api/search", json={"query": "phone", "filters": bad})
            assert resp.status_code == 422, bad


def test_unconfigured_search_is_503():
    # The real service, with no database or API key configured.
    app = create_app(Settings(_env_file=None, database_url=None, gemini_api_key=None))
    with TestClient(app) as client:
        resp = client.post("/api/search", json={"query": "sofa"})
    assert resp.status_code == 503
    assert "DATABASE_URL" in resp.json()["detail"]


def test_quota_exhausted_is_429_and_upstream_errors_are_502():
    with client_with(FakeService(QuotaExhaustedError("per day"))) as client:
        assert client.post("/api/search", json={"query": "sofa"}).status_code == 429
    with client_with(FakeService(RuntimeError("boom"))) as client:
        resp = client.post("/api/search", json={"query": "sofa"})
    assert resp.status_code == 502 and "boom" not in resp.text


def test_query_cache_key_ignores_whitespace_but_not_model_or_case():
    assert normalize_query("  used   iPhone\n15 ") == "used iPhone 15"
    a = cache_key("m", 1536, "task: search result | query: iphone")
    assert a == cache_key("m", 1536, "task: search result | query: iphone")
    assert a != cache_key("m2", 1536, "task: search result | query: iphone")
    assert a != cache_key("m", 768, "task: search result | query: iphone")
    assert a != cache_key("m", 1536, "task: search result | query: iPhone")


def test_ef_search_grows_with_limit():
    assert ef_search_for(10) == 40
    assert ef_search_for(50) == 100


def test_result_model_parses_jsonb_text():
    assert isinstance(to_result(LISTING), ListingResult)
