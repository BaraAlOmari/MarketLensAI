"""Exponential backoff with jitter for rate-limited provider calls (Gemini free tier)."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class QuotaExhaustedError(RuntimeError):
    """A daily quota was hit; retrying before it resets will not help."""


def status_of(exc: BaseException) -> int | None:
    # google-genai errors carry the HTTP status as `status_code` or `code`.
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def is_daily_quota(exc: BaseException) -> bool:
    text = str(exc).lower().replace(" ", "")
    return status_of(exc) == 429 and ("perday" in text or "daily" in text)


# google-genai's Interactions client wraps network failures in its own (private-module)
# APIConnectionError / APITimeoutError, raised from the underlying httpx error.
CONNECTION_ERROR_NAMES = {"APIConnectionError", "APITimeoutError"}


def causes(exc: BaseException):
    """The exception and everything it was explicitly raised from (`raise ... from`)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__


def is_retryable(exc: BaseException) -> bool:
    for e in causes(exc):
        if isinstance(e, httpx.TransportError | asyncio.TimeoutError | ConnectionError):
            return True
        if type(e).__name__ in CONNECTION_ERROR_NAMES:
            return True
    return status_of(exc) in RETRYABLE_STATUS


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 6,
    base_delay_s: float = 5.0,
    max_delay_s: float = 120.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Call `fn` until it succeeds, fails with a non-retryable error, or attempts run out."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if is_daily_quota(exc):
                raise QuotaExhaustedError(str(exc)) from exc
            if not is_retryable(exc) or attempt == max_attempts:
                raise
            delay = min(max_delay_s, base_delay_s * 2 ** (attempt - 1))
            delay *= random.uniform(0.75, 1.25)
            logger.warning(
                "retryable error (attempt %d/%d, status=%s): sleeping %.1fs",
                attempt,
                max_attempts,
                status_of(exc),
                delay,
            )
            await sleep(delay)
    raise AssertionError("unreachable")
