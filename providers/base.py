"""Abstract base class for all LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """All providers implement this interface."""

    name: str = "unknown"
    cost_per_1k_tokens: float = 0.0

    @abstractmethod
    def generate(self, prompt: dict[str, str]) -> str:
        """Call the model and return the raw completion string."""

    def health_check(self) -> bool:
        """Return True if the provider is reachable. Never raises."""
        return True
