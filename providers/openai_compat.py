"""Universal OpenAI-compatible provider — one class for every endpoint.

Chain (cost-ordered, 429-aware):
  Local:       Ollama → LM Studio → llamafile        (no key, free)
  Free cloud:  Groq → Gemini 2.0 Flash               (free-tier API keys)
  Paid:        OpenAI gpt-4o-mini → Mistral small     (optional fallback)
"""

from __future__ import annotations

import time

import httpx

from providers.base import BaseProvider

# Module-level health-check result cache: key → (result, monotonic_timestamp)
_health_cache: dict[str, tuple[bool, float]] = {}
_HEALTH_TTL = 30.0  # seconds

# (name, base_url, default_model, key_name, cost_per_1k, is_local)
# Server-side order: gemini first, then groq as 429 fallback
CATALOGUE: list[tuple[str, str, str, str | None, float, bool]] = [
    ("gemini",   "https://generativelanguage.googleapis.com/v1beta/openai",
                 "gemini-2.0-flash",          "gemini",   0.0,     False),
    ("groq",     "https://api.groq.com/openai/v1",
                 "llama-3.3-70b-versatile",   "groq",     0.0,     False),
    ("openai",   "https://api.openai.com/v1", "gpt-4o-mini",          "openai",   0.00015, False),
    ("mistral",  "https://api.mistral.ai/v1", "mistral-small-latest", "mistral",  0.0002,  False),
    ("ollama",   "http://localhost:11434/v1", "llama3",               None,       0.0,     True),
    ("lmstudio", "http://localhost:1234/v1",  "local-model",          None,       0.0,     True),
    ("llamafile","http://localhost:8080/v1",  "local-model",          None,       0.0,     True),
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
        cache_key = f"{self.name}:{self._base_url}"
        now = time.monotonic()
        if cache_key in _health_cache:
            cached_result, cached_at = _health_cache[cache_key]
            if now - cached_at < _HEALTH_TTL:
                return cached_result

        if self._is_local:
            try:
                r = self._client.get(f"{self._base_url}/models", timeout=2.0)
                result = r.status_code == 200
            except Exception:
                result = False
        else:
            # Cloud providers: reachable if a key is configured
            result = bool(self._api_key)

        _health_cache[cache_key] = (result, now)
        return result

    def generate(self, prompt: dict[str, str]) -> tuple[str, int]:
        """Call the LLM and return (content, tokens_used).

        tokens_used comes from response.usage.total_tokens (0 if not present).
        """
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
        if resp.status_code >= 400:  # noqa: PLR2004
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}: {resp.text}",
                request=resp.request,
                response=resp,
            )
        body = resp.json()
        content: str = body["choices"][0]["message"]["content"]
        tokens_used: int = body.get("usage", {}).get("total_tokens", 0)
        return content, tokens_used
