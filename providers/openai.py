"""OpenAI GPT cloud provider adapter."""

from __future__ import annotations

import httpx

from providers.base import BaseProvider

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(BaseProvider):
    name = "openai"
    cost_per_1k_tokens = 0.00015  # gpt-4o-mini input cost

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: dict[str, str]) -> str:
        resp = httpx.post(
            _API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
