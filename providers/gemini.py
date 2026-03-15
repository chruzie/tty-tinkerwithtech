"""Google Gemini cloud provider adapter."""

from __future__ import annotations

import httpx

from providers.base import BaseProvider

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(BaseProvider):
    name = "gemini"
    cost_per_1k_tokens = 0.000075  # Gemini 1.5 Flash input cost

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: dict[str, str]) -> str:
        url = _API_URL.format(model=self.model)
        resp = httpx.post(
            url,
            params={"key": self.api_key},
            json={
                "system_instruction": {"parts": [{"text": prompt["system"]}]},
                "contents": [{"parts": [{"text": prompt["user"]}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
