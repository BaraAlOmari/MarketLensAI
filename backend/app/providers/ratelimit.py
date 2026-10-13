"""Sliding-window limiter for per-minute provider quotas (requests or tokens)."""

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable


class SlidingWindowLimiter:
    """Allow at most `capacity` units in any `window_s` seconds; `acquire` waits for room."""

    def __init__(
        self,
        capacity: float,
        window_s: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.window_s = window_s
        self._clock = clock
        self._sleep = sleep
        self._events: deque[tuple[float, float]] = deque()
        self._used = 0.0

    def _expire(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= self.window_s:
            self._used -= self._events.popleft()[1]

    async def acquire(self, units: float) -> None:
        if units > self.capacity:
            raise ValueError(f"{units} units exceed the window capacity {self.capacity}")
        while True:
            now = self._clock()
            self._expire(now)
            if self._used + units <= self.capacity:
                self._events.append((now, units))
                self._used += units
                return
            await self._sleep(self._events[0][0] + self.window_s - now + 0.05)
