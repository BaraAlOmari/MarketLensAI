"""Stage 10: request IDs across streams, pipeline trace records, rate and size limits."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.answers.chat import Event
from app.api.chat import get_chat_service
from app.api.guard import RateLimiter, client_ip
from app.config import Settings
from app.logging_setup import request_id_var
from app.main import create_app
from app.models.filters import AttributeFilter, SearchFilters
from app.models.search import ListingResult, SearchRequest
from app.providers.query_cache import QueryVector
from app.retrieval.reranking import RerankOutcome
from app.retrieval.service import SearchService

chat_log = logging.getLogger("test.stream")


class StreamingChat:
    """Logs once before and once in the middle of its stream, like the real chat does."""

    async def events(self, message, session_id, filters=None):
        chat_log.info("before")
        yield Event("token", {"text": "a "})
        await asyncio.sleep(0)
        chat_log.info("during")
        yield Event("done", {"cited_ids": []})


class Capture(logging.Handler):
    """Records each log line's request ID as it is emitted."""

    def __init__(self):
        super().__init__()
        self.seen: list[tuple[str, str]] = []

    def emit(self, record):
        self.seen.append((record.getMessage(), request_id_var.get()))


def app_with(**settings):
    return create_app(Settings(_env_file=None, database_url=None, **settings))


def post_chat(client, **headers):
    return client.post("/api/chat", json={"session_id": "s1", "message": "phones"}, headers=headers)


def test_request_id_survives_into_the_streamed_body():
    app = app_with()
    app.dependency_overrides[get_chat_service] = lambda: StreamingChat()
    capture = Capture()
    chat_log.addHandler(capture)
    chat_log.setLevel(logging.INFO)
    try:
        with TestClient(app) as client:
            resp = post_chat(client, **{"x-request-id": "trace-abc-123"})
    finally:
        chat_log.removeHandler(capture)
    assert resp.headers["x-request-id"] == "trace-abc-123"
    # The record logged while the SSE body was streaming still carries the ID.
    assert capture.seen == [("before", "trace-abc-123"), ("during", "trace-abc-123")]


def test_rate_limit_answers_429_with_retry_after():
    app = app_with(rate_limit_per_minute=2)
    app.dependency_overrides[get_chat_service] = lambda: StreamingChat()
    with TestClient(app) as client:
        codes = [post_chat(client).status_code for _ in range(3)]
        limited = post_chat(client)
        health = client.get("/health")
    assert codes == [200, 200, 429]
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    assert "Too many searches" in limited.json()["detail"]
    assert health.status_code == 200  # /health is never limited


def test_rate_limit_can_be_switched_off():
    app = app_with(rate_limit_per_minute=1, rate_limit_enabled=False)
    app.dependency_overrides[get_chat_service] = lambda: StreamingChat()
    with TestClient(app) as client:
        assert [post_chat(client).status_code for _ in range(3)] == [200, 200, 200]


def test_sliding_windows_per_minute_and_per_day():
    limiter = RateLimiter(per_minute=2, per_day=3)
    assert [limiter.check("a", now=t).allowed for t in (0, 1, 2)] == [True, True, False]
    assert limiter.check("a", now=2).retry_after_s == 58  # the first hit leaves the minute
    assert limiter.check("b", now=2).allowed  # per client
    assert limiter.check("a", now=61).allowed  # third request of the day
    verdict = limiter.check("a", now=200)
    assert not verdict.allowed and verdict.retry_after_s == 86_400 - 200  # daily cap


def test_rate_limiter_memory_is_bounded():
    limiter = RateLimiter(per_minute=5, per_day=5, max_keys=3)
    for ip in "abcd":
        limiter.check(ip, now=0)
    assert list(limiter._hits) == ["b", "c", "d"]


def make_request(xff: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_client_ip_reads_only_trusted_forwarded_hops():
    assert client_ip(make_request("1.1.1.1"), 0) == "10.0.0.1"  # local: socket address
    # One proxy in front appended the client it saw; a forged entry before it is ignored.
    assert client_ip(make_request("6.6.6.6, 1.1.1.1"), 1) == "1.1.1.1"
    assert client_ip(make_request("1.1.1.1, 172.16.0.5"), 2) == "1.1.1.1"
    assert client_ip(make_request(None), 1) == "10.0.0.1"  # header missing: fall back


def test_request_body_size_is_limited():
    app = app_with(max_body_bytes=200)
    app.dependency_overrides[get_chat_service] = lambda: StreamingChat()
    big = {"session_id": "s1", "message": "x" * 300}
    with TestClient(app) as client:
        declared = client.post("/api/chat", json=big)

        def chunks():
            yield b'{"session_id": "s1", "message": "'
            yield b"x" * 300
            yield b'"}'

        chunked = client.post(
            "/api/chat", content=chunks(), headers={"content-type": "application/json"}
        )
        ok = post_chat(client)
    assert declared.status_code == 413 and chunked.status_code == 413
    assert ok.status_code == 200


def test_filter_sizes_are_capped():
    with pytest.raises(ValidationError):
        SearchFilters(models=[f"m{i}" for i in range(41)])
    with pytest.raises(ValidationError):
        SearchFilters(location="x" * 81)
    with pytest.raises(ValidationError):
        AttributeFilter(eq="y" * 81)
    SearchFilters(models=[f"m{i}" for i in range(32)], brands=["Apple"])  # a whole category


def listing(i: int, ranks: dict) -> ListingResult:
    return ListingResult(
        id=i, external_id=f"QA-{i}", title=f"Listing {i}", description="", category="phones",
        brand="Apple", model="iPhone 17", price="2000", currency="QAR", price_qar="2000",
        condition="good", listing_type="sale", price_period="total", attributes={},
        location="Doha", language="en", image_url=None, score=0.03, ranks=ranks,
    )  # fmt: skip


def test_search_trace_explains_every_result(caplog):
    service = SearchService(None, None, rrf_k=60)
    service.reranker = type("R", (), {"model": "fake-rerank"})()
    results = [
        listing(7, {"vector": 3, "keyword": 1, "rerank": 1}),
        listing(2, {"vector": 1, "rerank": 2}),
    ]
    filters = SearchFilters(category="phones", models=["iPhone 17"], keywords=["iPhone 17"])
    with caplog.at_level(logging.INFO, logger="app.retrieval.service"):
        service._log_trace(
            SearchRequest(query="used iPhone 17"), "hybrid", True,
            type("U", (), {"cached": True, "error": None, "guard_notes": (), "latency_ms": 0.0})(),
            filters, QueryVector("[0]", True, "q"), {"vector": 12, "keyword": 4},
            results, RerankOutcome(results=results, cached=False, latency_ms=900.0, ranked=2),
            results, {"retrieve": 300.0, "total": 1400.0},
        )  # fmt: skip
    by_event = {r.fields["event"]: r.fields for r in caplog.records}
    assert list(by_event) == [
        "search.understand",
        "search.retrieve",
        "search.rerank",
        "search.results",
    ]
    assert by_event["search.understand"]["filters"]["models"] == ["iPhone 17"]
    assert by_event["search.retrieve"]["candidates"] == {"vector": 12, "keyword": 4}
    assert by_event["search.retrieve"]["keyword_text"] == "iPhone 17"
    first, second = by_event["search.results"]["results"]
    assert first["external_id"] == "QA-7" and first["ranks"] == {
        "vector": 3,
        "keyword": 1,
        "rerank": 1,
    }
    assert "keyword" not in second["ranks"]  # found on meaning only
