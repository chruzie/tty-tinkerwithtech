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
        # Cache must contain a valid Ghostty-format theme (canonical format)
        tmp_repo.save_theme(query_hash=qh, theme_data=_VALID_THEME, input_type="prompt")

        result, tier = generate_from_prompt("ocean sunset", repo=tmp_repo)
        assert "palette" in result
        assert tier == 1

    def test_cache_hit_reserializes_to_requested_target(self, tmp_repo):
        """Tier-1 cache hit with Ghostty-cached data should return iTerm2 format when asked."""
        import hashlib

        from modes.prompt_mode import generate_from_prompt
        from security.input_sanitizer import sanitize_prompt

        q = sanitize_prompt("ocean sunset")
        qh = hashlib.sha256(q.encode()).hexdigest()
        # Seed cache in Ghostty (canonical) format
        tmp_repo.save_theme(query_hash=qh, theme_data=_VALID_THEME, input_type="prompt")

        result, tier = generate_from_prompt("ocean sunset", target="iterm2", repo=tmp_repo)
        # iTerm2 output is XML plist
        assert "<?xml" in result or "<plist" in result or "dict" in result
        assert tier == 1

    def test_llm_called_on_cache_miss(self, tmp_repo):
        from modes.prompt_mode import generate_from_prompt

        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.cost_per_1k_tokens = 0.0
        mock_provider.generate.return_value = _VALID_THEME

        with patch("cache.embeddings.embed", side_effect=ImportError):
            result, tier = generate_from_prompt(
                "cyberpunk rain", provider=mock_provider, repo=tmp_repo, skip_cache=False
            )

        assert "palette" in result
        assert tier == 3
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
            result, tier = generate_from_prompt(
                "retry test", provider=mock_provider, repo=tmp_repo, skip_cache=True
            )

        assert "palette" in result
        assert tier == 3
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
