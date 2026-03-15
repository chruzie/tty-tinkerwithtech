"""Anthropic Claude cloud provider adapter."""

from __future__ import annotations

import httpx

from providers.base import BaseProvider

_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    cost_per_1k_tokens = 0.00025  # Claude Haiku input cost

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: dict[str, str]) -> str:
        resp = httpx.post(
            _API_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "system": prompt["system"],
                "messages": [{"role": "user", "content": prompt["user"]}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
