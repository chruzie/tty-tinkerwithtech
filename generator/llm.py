"""Provider-agnostic LLM client."""

from __future__ import annotations


class LLMError(Exception):
    """Raised when the LLM call fails or returns an empty response."""


class LLMClient:
    """Thin wrapper that delegates generation to a provider object."""

    def generate(self, prompt: dict[str, str], provider: object) -> str:
        """Call the provider and return the raw theme string.

        Args:
            prompt: dict with "system" and "user" keys.
            provider: Any provider object with a generate(prompt) -> str method.

        Returns:
            The raw LLM output string (not yet validated).

        Raises:
            LLMError: if the provider raises or returns an empty string.
        """
        try:
            result: str = provider.generate(prompt)  # type: ignore[union-attr]
        except Exception as exc:
            raise LLMError(f"Provider error: {exc}") from exc

        if not result or not result.strip():
            raise LLMError("Provider returned an empty response")

        return result.strip()
