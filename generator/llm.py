"""Provider-agnostic LLM client."""

from __future__ import annotations


class LLMError(Exception):
    """Raised when the LLM call fails or returns an empty response."""


class LLMClient:
    """Thin wrapper that delegates generation to a provider object."""

    def generate(self, prompt: dict[str, str], provider: object) -> tuple[str, int]:
        """Call the provider and return (raw_theme_string, tokens_used).

        Args:
            prompt: dict with "system" and "user" keys.
            provider: Any provider with generate(prompt) -> (str, int).

        Returns:
            Tuple of (stripped LLM output, total tokens used).

        Raises:
            LLMError: if the provider raises or returns an empty string.
        """
        try:
            result, tokens = provider.generate(prompt)  # type: ignore[union-attr]
        except Exception as exc:
            raise LLMError(f"Provider error: {exc}") from exc

        if not result or not result.strip():
            raise LLMError("Provider returned an empty response")

        return result.strip(), tokens
