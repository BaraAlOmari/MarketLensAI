"""Abuse limits for the public API (Stage 10): request body size and per-IP rate limits.

The rate limit is a sliding window per client IP, kept in memory. With several instances each
keeps its own counts, which is fine for a demo: the point is that one client cannot burn the
shared free-tier model quota. `/health` is never limited.
"""

import logging
import math
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_setup import log_event

logger = logging.getLogger(__name__)

MINUTE = 60.0
DAY = 86_400.0


def client_ip(request: Request, forwarded_hops: int) -> str:
    """The client's address. With N trusted proxies in front, each appends the address it saw
    to X-Forwarded-For, so the client is the N-th entry from the right; entries further left
    were written by the client and could be anything."""
    if forwarded_hops > 0:
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",")]
        entries = [e for e in entries if e]
        if len(entries) >= forwarded_hops:
            return entries[-forwarded_hops]
    return request.client.host if request.client else "unknown"


@dataclass
class Verdict:
    allowed: bool
    retry_after_s: int = 0


class RateLimiter:
    """Two sliding windows per key: requests in the last minute and in the last day."""

    def __init__(self, per_minute: int, per_day: int, max_keys: int = 10_000) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self.max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def check(self, key: str, now: float | None = None) -> Verdict:
        now = time.monotonic() if now is None else now
        hits = self._hits.pop(key, None) or deque()
        while hits and hits[0] <= now - DAY:
            hits.popleft()
        self._hits[key] = hits  # most recently used last
        while len(self._hits) > self.max_keys:  # bounded memory: forget the oldest client
            self._hits.popitem(last=False)

        recent = sum(1 for t in hits if t > now - MINUTE)
        if recent >= self.per_minute:
            oldest_recent = next(t for t in hits if t > now - MINUTE)
            return Verdict(False, max(1, math.ceil(oldest_recent + MINUTE - now)))
        if len(hits) >= self.per_day:
            return Verdict(False, max(1, math.ceil(hits[0] + DAY - now)))
        hits.append(now)
        return Verdict(True)


async def rate_limited(request: Request) -> None:
    """Route dependency: 429 with Retry-After when the client is over its limit."""
    limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    ip = client_ip(request, request.app.state.settings.forwarded_hops)
    verdict = limiter.check(ip)
    if not verdict.allowed:
        # The client address is not logged; the request ID is enough to find the turn.
        log_event(logger, "request.rate_limited", path=request.url.path,
                  retry_after_s=verdict.retry_after_s)  # fmt: skip
        raise HTTPException(
            status_code=429,
            detail=f"Too many searches. Try again in {verdict.retry_after_s} seconds.",
            headers={"Retry-After": str(verdict.retry_after_s)},
        )


class BodySizeLimitMiddleware:
    """413 for request bodies over `max_bytes`, whether declared (Content-Length) or not
    (chunked): the body is counted as it arrives, before any route reads it."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await _too_large(send)
            return

        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # An HTTPException, because FastAPI turns any other error raised
                    # while reading the body into a generic 400.
                    raise HTTPException(status_code=413, detail="Request body too large")
            return message

        await self.app(scope, counted, send)


async def _too_large(send: Send) -> None:
    body = b'{"detail":"Request body too large"}'
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode())],
    })  # fmt: skip
    await send({"type": "http.response.body", "body": body})
