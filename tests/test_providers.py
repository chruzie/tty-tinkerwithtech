"""Tests for the simplified OpenAI-compatible provider layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestOpenAICompatProvider:
    def test_local_health_true(self):
        from providers.openai_compat import OpenAICompatProvider
        with patch("httpx.get") as m:
            m.return_value = MagicMock(status_code=200)
            p = OpenAICompatProvider("ollama", "http://localhost:11434/v1", "llama3", is_local=True)
            assert p.health_check() is True

    def test_local_health_false_on_error(self):
        from providers.openai_compat import OpenAICompatProvider
        with patch("httpx.get", side_effect=Exception("refused")):
            p = OpenAICompatProvider("ollama", "http://localhost:11434/v1", "llama3", is_local=True)
            assert p.health_check() is False

    def test_cloud_health_true_with_key(self):
        from providers.openai_compat import OpenAICompatProvider
        p = OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "llama3", api_key="key")
        assert p.health_check() is True

    def test_cloud_health_false_without_key(self):
        from providers.openai_compat import OpenAICompatProvider
        p = OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "llama3")
        assert p.health_check() is False

    def test_generate_returns_content(self):
        from providers.openai_compat import OpenAICompatProvider
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "palette = 0 = #000000"}}]}
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_resp):
            p = OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "llama3", api_key="k")
            assert p.generate({"system": "s", "user": "u"}) == "palette = 0 = #000000"


class TestRegistry:
    def test_resolve_prefers_local_running(self):
        from providers.registry import resolve_provider
        with (
            patch("httpx.get", return_value=MagicMock(status_code=200)),
            patch("security.keystore.get_key", return_value=None),
        ):
            p = resolve_provider()
            assert p.name == "ollama"

    def test_resolve_raises_when_nothing_available(self):
        from providers.registry import resolve_provider
        with (
            patch("httpx.get", side_effect=Exception("refused")),
            patch("security.keystore.get_key", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="No LLM provider"):
                resolve_provider()

    def test_fallback_on_429(self):
        import httpx

        from providers.registry import generate_with_fallback

        call_count = 0

        def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                r = MagicMock()
                r.status_code = 429
                raise httpx.HTTPStatusError("429", request=MagicMock(), response=r)
            m = MagicMock()
            m.raise_for_status = MagicMock()
            m.json.return_value = {"choices": [{"message": {"content": "theme output"}}]}
            return m

        with (
            patch("httpx.get", return_value=MagicMock(status_code=200)),
            patch("httpx.post", side_effect=fake_post),
            patch("security.keystore.get_key", return_value="fake-key"),
        ):
            result, provider_name = generate_with_fallback({"system": "s", "user": "u"})
            assert result == "theme output"
            assert call_count == 2
