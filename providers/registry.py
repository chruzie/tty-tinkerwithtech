"""Provider registry — resolves the first available provider (cost-ordered)."""

from __future__ import annotations

from providers.base import BaseProvider
from providers.llamafile import LlamafileProvider
from providers.lmstudio import LMStudioProvider
from providers.ollama import OllamaProvider
from security.keystore import get_key


def _cloud_providers() -> list[BaseProvider]:
    """Build cloud provider list from stored API keys (only those with keys set)."""
    providers: list[BaseProvider] = []

    # Import cloud providers lazily so missing packages don't break local-only usage
    from providers.anthropic import AnthropicProvider
    from providers.gemini import GeminiProvider
    from providers.groq import GroqProvider
    from providers.mistral import MistralProvider
    from providers.openai import OpenAIProvider

    for cls, key_name in [
        (GeminiProvider, "gemini"),
        (GroqProvider, "groq"),
        (AnthropicProvider, "anthropic"),
        (OpenAIProvider, "openai"),
        (MistralProvider, "mistral"),
    ]:
        key = get_key(key_name)
        if key:
            providers.append(cls(api_key=key))  # type: ignore[call-arg]

    return providers


def resolve_provider(preferred: str | None = None) -> BaseProvider:
    """Return the first healthy provider in the cost-ordered chain.

    Order: Ollama → LM Studio → llamafile → Gemini → Groq → Claude Haiku → GPT-4o-mini → Mistral

    Raises:
        RuntimeError: if no provider is available.
    """
    local: list[BaseProvider] = [
        OllamaProvider(),
        LMStudioProvider(),
        LlamafileProvider(),
    ]

    # If a preferred provider is specified, try it first
    if preferred:
        all_providers = local + _cloud_providers()
        for p in all_providers:
            if p.name == preferred:
                if p.health_check():
                    return p
                raise RuntimeError(f"Preferred provider {preferred!r} is not available")

    # Check local providers first (free)
    for p in local:
        if p.health_check():
            return p

    # Fall through to cloud
    for p in _cloud_providers():
        if p.health_check():
            return p

    raise RuntimeError(
        "No LLM provider available. Run Ollama locally or configure a cloud API key with "
        "'tty-theme config setup'."
    )
