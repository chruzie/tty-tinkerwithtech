"""Tests for prompt mode pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_VALID_THEME = "\n".join([
    f"palette = {i} = #{'ab'*3}" for i in range(16)
]) + "\nbackground = #0a0a0a\nforeground = #f0f0f0\ncursor-color = #f0f0f0\nselection-background = #1a1a1a\nselection-foreground = #f0f0f0"


@pytest.fixture
def tmp_repo():
    from cache.db import ThemeRepository
    with tempfile.TemporaryDirectory() as d:
        repo = ThemeRepository(db_path=Path(d) / "test.db")
        repo.init_db()
        yield repo


class TestPromptMode:
    def test_cache_hit_skips_llm(self, tmp_repo):
        import hashlib

        from modes.prompt_mode import generate_from_prompt
        from security.input_sanitizer import sanitize_prompt
        q = sanitize_prompt("ocean sunset")
        qh = hashlib.sha256(q.encode()).hexdigest()
        tmp_repo.save_theme(query_hash=qh, theme_data="cached-result", input_type="prompt")

        result = generate_from_prompt("ocean sunset", repo=tmp_repo)
        assert result == "cached-result"

    def test_llm_called_on_cache_miss(self, tmp_repo):
        from modes.prompt_mode import generate_from_prompt

        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.cost_per_1k_tokens = 0.0
        mock_provider.generate.return_value = _VALID_THEME

        with patch("cache.embeddings.embed", side_effect=ImportError):
            result = generate_from_prompt(
                "cyberpunk rain", provider=mock_provider, repo=tmp_repo, skip_cache=False
            )

        assert "palette" in result
        mock_provider.generate.assert_called_once()

    def test_retries_on_validation_failure(self, tmp_repo):
        from modes.prompt_mode import generate_from_prompt

        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.cost_per_1k_tokens = 0.0
        # First two calls return invalid, third is valid
        mock_provider.generate.side_effect = [
            "not valid",
            "also not valid",
            _VALID_THEME,
        ]

        with patch("cache.embeddings.embed", side_effect=ImportError):
            result = generate_from_prompt(
                "retry test", provider=mock_provider, repo=tmp_repo, skip_cache=True
            )

        assert "palette" in result
        assert mock_provider.generate.call_count == 3

    def test_max_retries_raises(self, tmp_repo):
        from modes.prompt_mode import generate_from_prompt

        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.cost_per_1k_tokens = 0.0
        mock_provider.generate.return_value = "always invalid"

        with pytest.raises(RuntimeError, match="failed after"):
            generate_from_prompt(
                "fail test", provider=mock_provider, repo=tmp_repo, skip_cache=True
            )
