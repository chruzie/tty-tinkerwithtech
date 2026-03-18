"""Per-IP daily rate limiting for LLM generation requests.

Limits:
- DAILY_GENERATION_LIMIT (env, default 5) generations per IP per day.
- Burst cooldowns trigger when > 3 requests within BURST_WINDOW_SECONDS (env, default 60).
  Cooldown schedule: 1st offense=10s, 2nd=30s, 3rd+=120s.

Only actual LLM calls count — cache hits (Tier 1 / Tier 2) bypass this entirely.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime

DAILY_GENERATION_LIMIT = int(os.environ.get("DAILY_GENERATION_LIMIT", "5"))
BURST_WINDOW_SECONDS = int(os.environ.get("BURST_WINDOW_SECONDS", "60"))
_BURST_THRESHOLD = 3
_BURST_COOLDOWNS = [10, 30, 120]  # seconds by offense index


class RateLimitExceeded(Exception):
    """Raised when the daily generation limit is reached."""

    def __init__(self, reset_at: datetime) -> None:
        self.reset_at = reset_at
        super().__init__(f"Daily limit reached. Resets at {reset_at.isoformat()}")


class BurstCooldown(Exception):
    """Raised when too many requests arrive in the burst window."""

    def __init__(self, cooldown_seconds: int) -> None:
        self.cooldown_seconds = cooldown_seconds
        super().__init__(f"Burst cooldown: {cooldown_seconds}s")


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def check_rate_limit(ip_hash: str, repo) -> None:  # noqa: ANN001
    """Check per-IP rate limits before an LLM generation call.

    Raises:
        RateLimitExceeded: daily count >= DAILY_GENERATION_LIMIT.
        BurstCooldown: too many requests within the burst window.
    """
    today = date.today().isoformat()
    now = _now_utc()
    state = repo.get_rate_limit(ip_hash)

    if state is None:
        return  # No history — allow

    daily_count = state.get("daily_count", 0)
    # get_rate_limit already returns 0 for daily_count when day != today
    if daily_count >= DAILY_GENERATION_LIMIT:
        # Reset happens at midnight UTC
        from datetime import timedelta

        reset_at = datetime.fromisoformat(today + "T00:00:00+00:00") + timedelta(days=1)
        raise RateLimitExceeded(reset_at=reset_at)

    # Burst check: count timestamps within the window
    raw_timestamps: str = state.get("burst_timestamps", "[]")
    timestamps: list[str] = (
        json.loads(raw_timestamps) if isinstance(raw_timestamps, str) else raw_timestamps
    )
    cutoff = now.timestamp() - BURST_WINDOW_SECONDS
    recent = [ts for ts in timestamps if datetime.fromisoformat(ts).timestamp() > cutoff]

    if len(recent) >= _BURST_THRESHOLD:
        offense_count = state.get("burst_offense_count", 0)
        cooldown_idx = min(offense_count, len(_BURST_COOLDOWNS) - 1)
        raise BurstCooldown(cooldown_seconds=_BURST_COOLDOWNS[cooldown_idx])


def increment_rate_limit(ip_hash: str, repo) -> None:  # noqa: ANN001
    """Increment the daily count and record timestamp for burst tracking."""
    today = date.today().isoformat()
    now = _now_utc()
    state = repo.get_rate_limit(ip_hash) or {}

    # Reset daily count if day changed
    if state.get("day") != today:
        daily_count = 1
        burst_timestamps: list[str] = []
        burst_offense_count = state.get("burst_offense_count", 0)
    else:
        daily_count = state.get("daily_count", 0) + 1
        raw = state.get("burst_timestamps", "[]")
        burst_timestamps = json.loads(raw) if isinstance(raw, str) else list(raw)
        burst_offense_count = state.get("burst_offense_count", 0)

    # Prune old burst timestamps (keep only within window)
    cutoff = now.timestamp() - BURST_WINDOW_SECONDS
    burst_timestamps = [
        ts for ts in burst_timestamps if datetime.fromisoformat(ts).timestamp() > cutoff
    ]
    burst_timestamps.append(now.isoformat())

    # Increment offense count if this is a burst event
    if len(burst_timestamps) > _BURST_THRESHOLD:
        burst_offense_count += 1

    repo.upsert_rate_limit(
        ip_hash=ip_hash,
        daily_count=daily_count,
        day=today,
        burst_timestamps=burst_timestamps,
        burst_offense_count=burst_offense_count,
    )
