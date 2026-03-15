"""Tests for FastAPI endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_VALID_THEME = "\n".join([
    f"palette = {i} = #{'ab'*3}" for i in range(16)
]) + "\nbackground = #0a0a0a\nforeground = #f0f0f0\ncursor-color = #f0f0f0\nselection-background = #1a1a1a\nselection-foreground = #f0f0f0"


@pytest.fixture
def client():
    from httpx import ASGITransport, AsyncClient

    from api.main import app
    from cache.db import ThemeRepository

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
async def test_generate_with_mock_provider(client):
    mock_provider = MagicMock()
    mock_provider.name = "mock"
    mock_provider.cost_per_1k_tokens = 0.0
    mock_provider.generate.return_value = _VALID_THEME

    with (
        patch("providers.registry.resolve_provider", return_value=mock_provider),
        patch("cache.embeddings.embed", side_effect=ImportError),
    ):
        async with client as c:
            resp = await c.post(
                "/v1/generate",
                json={"prompt": "tokyo night", "target": "ghostty"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "theme" in data
        assert data["provider"] == "mock"


@pytest.mark.asyncio
async def test_generate_missing_prompt_or_image(client):
    async with client as c:
        resp = await c.post("/v1/generate", json={"target": "ghostty"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_invalid_target(client):
    async with client as c:
        resp = await c.post(
            "/v1/generate",
            json={"prompt": "test", "target": "windows_terminal"},
        )
    assert resp.status_code == 422
