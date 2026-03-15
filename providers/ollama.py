"""Ollama local provider adapter."""

from __future__ import annotations

import httpx

from providers.base import BaseProvider

_BASE_URL = "http://localhost:11434"


class OllamaProvider(BaseProvider):
    name = "ollama"
    cost_per_1k_tokens = 0.0

    def __init__(self, model: str = "llama3") -> None:
        self.model = model

    def health_check(self) -> bool:
        try:
            r = httpx.get(f"{_BASE_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: dict[str, str]) -> str:
        resp = httpx.post(
            f"{_BASE_URL}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                "temperature": 0.7,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
