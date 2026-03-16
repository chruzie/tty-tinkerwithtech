"""Provider registry — resolves providers with 429-aware auto-fallback.

Resolution order (cost-ordered):
  1. Local: Ollama → LM Studio → llamafile  (health-checked, no key needed)
  2. Free cloud: Groq → Gemini              (tried in order; 429 → next)
  3. Paid: OpenAI → Mistral                 (only if key configured)

On HTTP 429 (throttled), the registry transparently tries the next provider.
All other errors propagate immediately.
"""

from __future__ import annotations

import httpx

from providers.openai_compat import CATALOGUE, OpenAICompatProvider
from security.keystore import get_key


def _build_chain(preferred: str | None = None) -> list[OpenAICompatProvider]:
    """Build the ordered provider list, injecting stored API keys."""
    providers: list[OpenAICompatProvider] = []

    for name, base_url, model, key_name, cost, is_local in CATALOGUE:
        api_key = get_key(key_name) if key_name else None
        p = OpenAICompatProvider(
            name=name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            cost_per_1k=cost,
            is_local=is_local,
        )
        providers.append(p)

    # If a preferred provider is requested, move it to the front
    if preferred:
        providers.sort(key=lambda p: (0 if p.name == preferred else 1))

    return providers


def resolve_provider(preferred: str | None = None) -> OpenAICompatProvider:
    """Return first healthy provider; skip local providers that aren't running.

    Raises:
        RuntimeError: if no provider is healthy/configured.
    """
    chain = _build_chain(preferred)
    available = [p for p in chain if p.health_check()]

    if not available:
        raise RuntimeError(
            "No LLM provider available.\n"
            "• Local: start Ollama (`ollama serve`) or LM Studio\n"
            "• Free cloud: run `tty-theme config setup` to add a Groq or Gemini API key"
        )

    return available[0]


def generate_with_fallback(
    prompt: dict[str, str],
    preferred: str | None = None,
) -> tuple[str, str, int]:
    """Generate a theme string with automatic 429 fallback across providers.

    Returns:
        (theme_str, provider_name, tokens_used) — raw LLM output, provider, and token count.

    Raises:
        RuntimeError: if all available providers are exhausted (throttled or failed).
    """
    chain = _build_chain(preferred)
    available = [p for p in chain if p.health_check()]

    if not available:
        raise RuntimeError(
            "No LLM provider available. Run `tty-theme config setup` to configure one."
        )

    errors: list[str] = []
    for provider in available:
        try:
            content, tokens = provider.generate(prompt)
            return content, provider.name, tokens
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:  # noqa: PLR2004
                errors.append(f"{provider.name}: throttled (429)")
                continue  # try next provider
            raise  # non-429 HTTP error: propagate immediately
        except httpx.RequestError as exc:
            errors.append(f"{provider.name}: connection error ({exc})")
            continue

    raise RuntimeError(
        "All providers exhausted:\n" + "\n".join(f"  • {e}" for e in errors)
    )
