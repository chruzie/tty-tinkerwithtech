"""Tests for FastAPI endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_VALID_THEME = "\n".join([
    f"palette = {i} = #{'ab'*3}" for i in range(16)
]) + "\nbackground = #0a0a0a\nforeground = #f0f0f0\ncursor-color = #f0f0f0\nselection-background = #1a1a1a\nselection-foreground = #f0f0f0"


@pytest.fixture
def client():
    from httpx import ASGITransport, AsyncClient

    from api.main import app
    from api.middleware import _hour_buckets, _minute_buckets
    from cache.db import ThemeRepository

    # Reset token-bucket state so tests don't share quota across runs
    _minute_buckets.clear()
    _hour_buckets.clear()

    with tempfile.TemporaryDirectory() as d:
        repo = ThemeRepository(db_path=Path(d) / "test.db")
        repo.init_db()
        app.state.repo = repo

        transport = ASGITransport(app=app)
        yield AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    async with client as c:
        resp = await c.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_v1(client):
    async with client as c:
        resp = await c.get("/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_generate_returns_theme_data_and_slug(client):
    with (
        patch("providers.registry.generate_with_fallback", return_value=(_VALID_THEME, "gemini")),
        patch("generator.validator.validate_theme", return_value=None),
        patch("cache.embeddings.embed", side_effect=ImportError),
    ):
        async with client as c:
            resp = await c.post("/v1/generate", json={"prompt": "tokyo night"})
        assert resp.status_code == 200
        data = resp.json()
        assert "theme_data" in data
        assert "slug" in data
        assert data["cached"] is False
        assert data["provider"] == "gemini"


@pytest.mark.asyncio
async def test_generate_201_char_prompt_returns_400(client):
    async with client as c:
        resp = await c.post("/v1/generate", json={"prompt": "a" * 201})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "prompt_too_long"


@pytest.mark.asyncio
async def test_generate_sixth_request_returns_429(client):
    """6th LLM generation from same IP must return 429 (daily limit reached)."""
    from datetime import date

    # Pre-seed the rate limit at exactly the daily cap so the next call is blocked
    IP = "testip9999"
    today = date.today().isoformat()

    async with client as c:
        # Seed the repo state directly (bypasses burst detection)
        app = c._transport.app  # type: ignore[attr-defined]
        repo = app.state.repo
        repo.upsert_rate_limit(IP, 5, today, [], 0)

        with patch("api.main._ip_hash", return_value=IP):
            r = await c.post("/v1/generate", json={"prompt": "any prompt"})

    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_list_themes_returns_pagination(client):
    async with client as c:
        resp = await c.get("/v1/themes")
    assert resp.status_code == 200
    data = resp.json()
    assert "themes" in data
    assert "total" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_get_theme_by_slug_not_found(client):
    async with client as c:
        resp = await c.get("/v1/themes/nonexistent-slug")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_theme_returns_201(client):
    async with client as c:
        resp = await c.post(
            "/v1/themes",
            json={"name": "My Theme", "theme_data": _VALID_THEME},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "my-theme"


@pytest.mark.asyncio
async def test_publish_duplicate_returns_409(client):
    async with client as c:
        await c.post("/v1/themes", json={"name": "Dup", "theme_data": _VALID_THEME})
        resp = await c.post("/v1/themes", json={"name": "Dup", "theme_data": _VALID_THEME})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_download_increments_count(client):
    async with client as c:
        await c.post("/v1/themes", json={"name": "Dl Theme", "theme_data": _VALID_THEME})
        resp = await c.post("/v1/themes/dl-theme/download")
    assert resp.status_code == 200
    assert resp.json()["download_count"] == 1


@pytest.mark.asyncio
async def test_neofetch_not_found(client):
    async with client as c:
        resp = await c.get("/v1/neofetch/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_neofetch_returns_real_colors(client):
    """Regression: palette = N = #hex lines must be parsed correctly (not grey fallback)."""
    async with client as c:
        # Publish a theme with known palette color 0 = #ff0000
        theme = "\n".join(
            [f"palette = {i} = #ff{i:02x}{i:02x}" for i in range(16)]
        ) + "\nbackground = #0a0a0a\nforeground = #f0f0f0\ncursor-color = #f0f0f0\nselection-background = #1a1a1a\nselection-foreground = #f0f0f0"
        await c.post("/v1/themes", json={"name": "Neofetch Test", "theme_data": theme})
        resp = await c.get("/v1/neofetch/neofetch-test")
    assert resp.status_code == 200
    body = resp.text
    # Color 0 is #ff0000 → R=255,G=0,B=0 → ANSI escape must contain "255;0;0"
    assert "255;0;0" in body
