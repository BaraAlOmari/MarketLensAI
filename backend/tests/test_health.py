from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client() -> TestClient:
    # _env_file=None keeps a developer's local backend/.env out of the tests.
    return TestClient(create_app(Settings(_env_file=None, database_url=None)))


def test_health_ok_without_database():
    with make_client() as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "MarketLens"
    assert body["database"] == {"configured": False, "ok": False, "pgvector": None}


def test_request_id_is_echoed():
    with make_client() as client:
        resp = client.get("/health", headers={"x-request-id": "abc123"})
    assert resp.headers["x-request-id"] == "abc123"


def test_request_id_is_generated():
    with make_client() as client:
        resp = client.get("/health")
    assert len(resp.headers["x-request-id"]) == 32
