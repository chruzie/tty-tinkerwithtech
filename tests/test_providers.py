"""Tests for provider adapters and registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestLocalProviders:
    def test_ollama_health_check_true(self):
        from providers.ollama import OllamaProvider

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            p = OllamaProvider()
            assert p.health_check() is True

    def test_ollama_health_check_false_on_error(self):
        from providers.ollama import OllamaProvider

        with patch("httpx.get", side_effect=Exception("refused")):
            p = OllamaProvider()
            assert p.health_check() is False

    def test_ollama_generate(self):
        from providers.ollama import OllamaProvider

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "palette = 0 = #000000"}}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            p = OllamaProvider()
            result = p.generate({"system": "sys", "user": "usr"})
            assert result == "palette = 0 = #000000"

    def test_lmstudio_health_false_on_error(self):
        from providers.lmstudio import LMStudioProvider

        with patch("httpx.get", side_effect=ConnectionError):
            p = LMStudioProvider()
            assert p.health_check() is False

    def test_llamafile_health_false_on_error(self):
        from providers.llamafile import LlamafileProvider

        with patch("httpx.get", side_effect=ConnectionError):
            p = LlamafileProvider()
            assert p.health_check() is False


class TestRegistry:
    def test_resolve_prefers_local(self):
        from providers.registry import resolve_provider

        with (
            patch("providers.ollama.OllamaProvider.health_check", return_value=True),
        ):
            p = resolve_provider()
            assert p.name == "ollama"

    def test_resolve_raises_when_nothing_available(self):
        from providers.registry import resolve_provider

        with (
            patch("providers.ollama.OllamaProvider.health_check", return_value=False),
            patch("providers.lmstudio.LMStudioProvider.health_check", return_value=False),
            patch("providers.llamafile.LlamafileProvider.health_check", return_value=False),
            patch("security.keystore.get_key", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="No LLM provider"):
                resolve_provider()
