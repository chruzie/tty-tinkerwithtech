"""Tests for api/rate_limit.py and cache/db.py rate_limits methods."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cache.db import ThemeRepository
from api.rate_limit import (
    BurstCooldown,
    RateLimitExceeded,
    check_rate_limit,
    increment_rate_limit,
)


@pytest.fixture
def repo(tmp_path: Path) -> ThemeRepository:
    r = ThemeRepository(db_path=tmp_path / "test.db")
    r.init_db()
    return r


# ── DB layer tests (US-007) ────────────────────────────────────────────────────

def test_upsert_then_get_returns_values(repo: ThemeRepository) -> None:
    today = date.today().isoformat()
    repo.upsert_rate_limit("aabbccdd", 3, today, [f"{today}T12:00:00+00:00"], 0)
    state = repo.get_rate_limit("aabbccdd")
    assert state is not None
    assert state["daily_count"] == 3
    assert state["burst_offense_count"] == 0


def test_day_mismatch_returns_zero_count(repo: ThemeRepository) -> None:
    repo.upsert_rate_limit("aabbccdd", 5, "2020-01-01", [], 0)
    state = repo.get_rate_limit("aabbccdd")
    assert state is not None
    assert state["daily_count"] == 0  # old day — count reset to 0


def test_get_rate_limit_missing_returns_none(repo: ThemeRepository) -> None:
    assert repo.get_rate_limit("unknown") is None


# ── Rate limit logic tests (US-006) ────────────────────────────────────────────

def test_five_calls_succeed(repo: ThemeRepository) -> None:
    import api.rate_limit as rl

    ip = "testip0001"
    # Disable burst window so rapid sequential calls don't trigger BurstCooldown
    with patch.object(rl, "BURST_WINDOW_SECONDS", 0):
        for _ in range(5):
            check_rate_limit(ip, repo)
            increment_rate_limit(ip, repo)
    # 5th call should have succeeded without raising


def test_sixth_call_raises_rate_limit_exceeded(repo: ThemeRepository) -> None:
    import api.rate_limit as rl

    ip = "testip0002"
    with patch.object(rl, "BURST_WINDOW_SECONDS", 0):
        for _ in range(5):
            check_rate_limit(ip, repo)
            increment_rate_limit(ip, repo)
        with pytest.raises(RateLimitExceeded):
            check_rate_limit(ip, repo)


def test_burst_triggers_cooldown(repo: ThemeRepository) -> None:
    """4 requests within burst window should trigger BurstCooldown on 4th."""
    ip = "testip0003"
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    # Seed 3 recent timestamps directly
    repo.upsert_rate_limit(ip, 3, "2026-03-15", [now_iso, now_iso, now_iso], 0)

    with pytest.raises(BurstCooldown) as exc_info:
        check_rate_limit(ip, repo)
    assert exc_info.value.cooldown_seconds == 10  # first offense
