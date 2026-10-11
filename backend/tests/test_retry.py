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
