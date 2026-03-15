"""Tests for /metrics endpoint auth (US-004)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


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
async def test_metrics_no_token_env_allows_access(client):
    """When METRICS_TOKEN is not set, /metrics is accessible without auth."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure METRICS_TOKEN is absent
        import os
        os.environ.pop("METRICS_TOKEN", None)

        async with client as c:
            resp = await c.get("/metrics")
        # prometheus_client may not be installed — 404 is fine; 403 is not
        assert resp.status_code != 403


@pytest.mark.asyncio
async def test_metrics_with_token_requires_auth(client):
    """When METRICS_TOKEN is set, /metrics returns 403 without correct header."""
    with patch.dict("os.environ", {"METRICS_TOKEN": "secret123"}):
        async with client as c:
            resp = await c.get("/metrics")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metrics_with_token_wrong_token_rejected(client):
    """Wrong bearer token is rejected with 403."""
    with patch.dict("os.environ", {"METRICS_TOKEN": "secret123"}):
        async with client as c:
            resp = await c.get("/metrics", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metrics_with_token_correct_token_allowed(client):
    """Correct bearer token allows access."""
    with patch.dict("os.environ", {"METRICS_TOKEN": "secret123"}):
        async with client as c:
            resp = await c.get("/metrics", headers={"Authorization": "Bearer secret123"})
        # 200 if prometheus_client installed, 404 if not — but NOT 403
        assert resp.status_code != 403
