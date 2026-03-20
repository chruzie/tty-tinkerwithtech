"""Tests for cache/db.py."""

import json
from pathlib import Path

import pytest

from cache.db import ThemeRepository


@pytest.fixture
def repo(tmp_path: Path) -> ThemeRepository:
    r = ThemeRepository(db_path=tmp_path / "test.db")
    r.init_db()
    return r


def test_init_db_idempotent(repo: ThemeRepository) -> None:
    repo.init_db()  # second call must not raise
    repo.init_db()  # third call must not raise


def test_save_and_retrieve_by_hash(repo: ThemeRepository) -> None:
    theme_data = "palette = 0=#1a1a2e\nbackground = #1a1a2e"
    row_id = repo.save_theme(
        query_hash="abc123",
        theme_data=theme_data,
        input_type="prompt",
        provider="ollama",
        cost_usd=0.0,
    )
    assert row_id == 1

    result = repo.get_by_hash("abc123")
    assert result is not None
    assert result["theme_data"] == theme_data
    assert result["input_type"] == "prompt"


def test_get_by_hash_missing_returns_none(repo: ThemeRepository) -> None:
    assert repo.get_by_hash("nonexistent") is None


def test_save_with_embedding_roundtrip(repo: ThemeRepository) -> None:
    embedding = [0.1, 0.2, 0.3, 0.4]
    repo.save_theme(
        query_hash="emb_test",
        theme_data="background = #000000",
        input_type="prompt",
        embedding=embedding,
    )
    pairs = repo.get_all_embeddings()
    assert len(pairs) == 1
    row_id, vector = pairs[0]
    assert row_id == 1
    assert len(vector) == 4
    assert abs(vector[0] - 0.1) < 1e-6


def test_embedding_stored_as_json(repo: ThemeRepository, tmp_path: Path) -> None:
    """Confirm embedding column is a JSON string, not binary."""
    embedding = [1.0, 2.0]
    repo.save_theme(
        query_hash="json_check",
        theme_data="background = #000000",
        input_type="prompt",
        embedding=embedding,
    )
    row = repo.get_by_hash("json_check")
    assert row is not None
    # embedding must be parseable as JSON
    parsed = json.loads(row["embedding"])
    assert parsed == embedding


def test_log_cost_and_daily_spend(repo: ThemeRepository) -> None:
    assert repo.get_daily_spend() == 0.0
    repo.log_cost("gemini", 0.0005)
    repo.log_cost("gemini", 0.0005)
    repo.log_cost("haiku", 0.001)
    total = repo.get_daily_spend()
    assert abs(total - 0.002) < 1e-9


def test_log_cost_upsert_is_atomic(repo: ThemeRepository) -> None:
    """ON CONFLICT upsert must accumulate calls and cost without duplicates."""
    repo.log_cost("groq", 0.001)
    repo.log_cost("groq", 0.001)
    repo.log_cost("groq", 0.001)
    total = repo.get_daily_spend()
    assert abs(total - 0.003) < 1e-9

    # Verify the row count is exactly 1 (no duplicates)
    import sqlite3

    with sqlite3.connect(repo.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM cost_log WHERE provider = 'groq'").fetchone()[0]
    assert count == 1


def test_list_themes(repo: ThemeRepository) -> None:
    for i in range(3):
        repo.save_theme(
            query_hash=f"hash_{i}",
            theme_data=f"background = #00000{i}",
            input_type="prompt",
        )
    themes = repo.list_themes()
    assert len(themes) == 3


def test_find_similar_accepts_str_ids() -> None:
    """find_similar must return the str ID unchanged (Firestore compat).

    Firestore uses str document IDs; find_similar must propagate the ID type
    through to the caller so get_by_id(str_id) can be called without int().
    """
    from unittest.mock import patch

    from cache.embeddings import find_similar

    # Simulate Firestore-style str IDs in the candidates list
    candidates: list[tuple[int | str, list[float]]] = [
        ("doc-abc", [1.0, 0.0]),
        ("doc-xyz", [0.0, 1.0]),
    ]
    query_vec = [1.0, 0.0]  # cosine sim = 1.0 with doc-abc

    with patch("cache.embeddings.embed", return_value=query_vec):
        result = find_similar("test query", candidates, threshold=0.85)

    assert result == "doc-abc"
    assert isinstance(result, str)
