"""FastAPI middleware — per-IP rate limiting and audit logging."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable

from cachetools import TTLCache
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── Token bucket store (in-process; swap to Redis for multi-replica) ──────────

class _TokenBucket:
    def __init__(self, capacity: float, rate: float) -> None:
        self.capacity = capacity
        self.rate = rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def available(self) -> bool:
        """Return True if a token is available without consuming it."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        projected = min(self.capacity, self.tokens + elapsed * self.rate)
        return projected >= 1.0

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


_minute_buckets: TTLCache = TTLCache(maxsize=10000, ttl=3600)
_hour_buckets: TTLCache = TTLCache(maxsize=10000, ttl=3600)


def _get_minute_bucket(ip_hash: str) -> _TokenBucket:
    if ip_hash not in _minute_buckets:
        _minute_buckets[ip_hash] = _TokenBucket(10, 10 / 60)
    return _minute_buckets[ip_hash]  # type: ignore[return-value]


def _get_hour_bucket(ip_hash: str) -> _TokenBucket:
    if ip_hash not in _hour_buckets:
        _hour_buckets[ip_hash] = _TokenBucket(50, 50 / 3600)
    return _hour_buckets[ip_hash]  # type: ignore[return-value]


def _ip_hash(request: Request) -> str:
    trusted_proxy_count = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    host = request.client.host if request.client else "unknown"

    if trusted_proxy_count == 0:
        ip = host
    else:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",")]
            # Pick the Nth-from-right entry added by the trusted proxy chain.
            # index = max(0, len(parts) - trusted_proxy_count) gives the leftmost
            # IP injected by the outermost trusted hop.
            idx = max(0, len(parts) - trusted_proxy_count)
            ip = parts[idx]
        else:
            ip = host

    return hashlib.sha256(ip.encode()).hexdigest()[:16]


# ── Rate limit middleware ──────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        ip_hash = _ip_hash(request)

        minute_bucket = _get_minute_bucket(ip_hash)
        hour_bucket = _get_hour_bucket(ip_hash)
        # Check both buckets before consuming either so a full hour quota
        # never silently burns a minute token (BUG-07).
        if not minute_bucket.available() or not hour_bucket.available():
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                headers={"Retry-After": "60", "Content-Type": "application/json"},
            )
        minute_bucket.consume()
        hour_bucket.consume()

        return await call_next(request)


# ── Audit log middleware ───────────────────────────────────────────────────────

class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if request.url.path == "/v1/generate":
            ip_hash = _ip_hash(request)
            try:
                repo = request.app.state.repo
                repo.log_audit(
                    ip_hash=ip_hash,
                    query_hash="",
                    input_type="unknown",
                    provider="unknown",
                    tier_used=0,
                    cost_usd=0.0,
                    status=str(response.status_code),
                )
            except Exception:  # noqa: BLE001, S110
                pass  # Never let audit failure break the response

        return response
