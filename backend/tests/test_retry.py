import httpx
import pytest

from app.providers.retry import QuotaExhaustedError, with_retries


class FakeAPIError(Exception):
    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message)
        self.code = code


async def no_sleep(_: float) -> None:
    return None


async def test_retries_rate_limit_then_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise FakeAPIError(429, "GenerateRequestsPerMinutePerProjectPerModel")
        return "ok"

    assert await with_retries(fn, sleep=no_sleep) == "ok"
    assert len(calls) == 3


async def test_daily_quota_stops_immediately():
    async def fn():
        raise FakeAPIError(429, "Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    with pytest.raises(QuotaExhaustedError):
        await with_retries(fn, sleep=no_sleep)


async def test_client_error_is_not_retried():
    calls = []

    async def fn():
        calls.append(1)
        raise FakeAPIError(400, "bad request")

    with pytest.raises(FakeAPIError):
        await with_retries(fn, sleep=no_sleep)
    assert len(calls) == 1


async def test_gives_up_after_max_attempts():
    calls = []

    async def fn():
        calls.append(1)
        raise FakeAPIError(503)

    with pytest.raises(FakeAPIError):
        await with_retries(fn, max_attempts=3, sleep=no_sleep)
    assert len(calls) == 3


class APIConnectionError(Exception):
    """Same name as google-genai's private wrapper for network failures."""


async def test_wrapped_connection_error_is_retried():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            try:
                raise httpx.ReadError("connection reset")
            except httpx.ReadError as exc:
                raise APIConnectionError("Connection error.") from exc
        return "ok"

    assert await with_retries(fn, sleep=no_sleep) == "ok"
    assert len(calls) == 2


async def test_error_merely_raised_during_a_network_error_is_not_retried():
    calls = []

    async def fn():
        calls.append(1)
        try:
            raise httpx.ReadError("connection reset")
        except httpx.ReadError:
            raise FakeAPIError(400, "bad request")  # noqa: B904 (implicit context on purpose)

    with pytest.raises(FakeAPIError):
        await with_retries(fn, sleep=no_sleep)
    assert len(calls) == 1
