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
    prompt: str,
    system: str,
    preferred: str | None = None,
) -> str:
    """Generate a theme string with automatic 429 fallback across providers.

    Tries gemini first (server-side default), then groq on HTTP 429.
    Non-429 errors propagate immediately.

    Args:
        prompt: User-turn text (already wrapped by build_user_prompt).
        system: System prompt string.
        preferred: Optional provider name to try first.

    Returns:
        Raw LLM output string.

    Raises:
        RuntimeError: if all available providers are exhausted (throttled or failed).
    """
    prompt_dict = {"system": system, "user": prompt}
    chain = _build_chain(preferred)
    available = [p for p in chain if p.health_check()]

    if not available:
        raise RuntimeError(
            "No LLM provider available. Configure GEMINI_API_KEY or GROQ_API_KEY."
        )

    errors: list[str] = []
    for provider in available:
        try:
            content, _tokens = provider.generate(prompt_dict)
            return content
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
