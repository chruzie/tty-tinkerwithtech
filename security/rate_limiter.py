"""Token-bucket rate limiter for CLI and API usage."""

from __future__ import annotations

import time


class RateLimiter:
    """Token-bucket rate limiter.

    Tokens replenish at *rate* per second up to *capacity*.
    Each call to :meth:`check` consumes one token.
    """

    def __init__(self, capacity: float = 10.0, rate: float = 1.0) -> None:
        self._capacity = capacity
        self._rate = rate  # tokens per second
        self._tokens = capacity
        self._last: float = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last = now

    def check(self) -> bool:
        """Consume one token. Returns True if allowed, False if throttled."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_and_check(self) -> None:
        """Block until a token is available, then consume it."""
        while not self.check():
            time.sleep(0.05)
