"""Universal OpenAI-compatible provider — one class for every endpoint.

Chain (cost-ordered, 429-aware):
  Local:       Ollama → LM Studio → llamafile        (no key, free)
  Free cloud:  Groq → Gemini 2.0 Flash               (free-tier API keys)
  Paid:        OpenAI gpt-4o-mini → Mistral small     (optional fallback)
"""

from __future__ import annotations

import httpx

from providers.base import BaseProvider

# (name, base_url, default_model, key_name, cost_per_1k, is_local)
CATALOGUE: list[tuple[str, str, str, str | None, float, bool]] = [
    ("ollama",   "http://localhost:11434/v1", "llama3",               None,       0.0,     True),
    ("lmstudio", "http://localhost:1234/v1",  "local-model",          None,       0.0,     True),
    ("llamafile","http://localhost:8080/v1",  "local-model",          None,       0.0,     True),
    ("groq",     "https://api.groq.com/openai/v1",
                 "llama-3.1-8b-instant",      "groq",     0.0,     False),
    ("gemini",   "https://generativelanguage.googleapis.com/v1beta/openai",
                 "gemini-2.0-flash",          "gemini",   0.0,     False),
    ("openai",   "https://api.openai.com/v1", "gpt-4o-mini",          "openai",   0.00015, False),
    ("mistral",  "https://api.mistral.ai/v1", "mistral-small-latest", "mistral",  0.0002,  False),
]


class OpenAICompatProvider(BaseProvider):
    """Single provider class for every OpenAI-compatible LLM endpoint."""

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        cost_per_1k: float = 0.0,
        is_local: bool = False,
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self.cost_per_1k_tokens = cost_per_1k
        self._is_local = is_local
        self._client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        """Release the underlying httpx connection pool."""
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001, S110
            pass

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def health_check(self) -> bool:
        if self._is_local:
            try:
                r = self._client.get(f"{self._base_url}/models", timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False
        # Cloud providers: reachable if a key is configured
        return bool(self._api_key)

    def generate(self, prompt: dict[str, str]) -> str:
        resp = self._client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user",   "content": prompt["user"]},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            },
        )
        resp.raise_for_status()  # raises HTTPStatusError (incl. 429) — caught by registry
        return resp.json()["choices"][0]["message"]["content"]
