"""Abstract base class for terminal theme serializers."""

from __future__ import annotations

from abc import ABC, abstractmethod

# All 21 required Ghostty theme keys
REQUIRED_KEYS: frozenset[str] = frozenset({
    "palette = 0", "palette = 1", "palette = 2", "palette = 3",
    "palette = 4", "palette = 5", "palette = 6", "palette = 7",
    "palette = 8", "palette = 9", "palette = 10", "palette = 11",
    "palette = 12", "palette = 13", "palette = 14", "palette = 15",
    "background", "foreground", "cursor-color",
    "selection-background", "selection-foreground",
})


class ThemeSerializer(ABC):
    """Convert a normalized palette dict to a terminal-specific format."""

    @abstractmethod
    def serialize(self, palette: dict[str, str]) -> str:
        """Serialize palette to a target-specific string.

        Args:
            palette: mapping of Ghostty key names → #RRGGBB hex strings.

        Returns:
            The formatted theme string ready to write to disk.

        Raises:
            ValueError: if a required key is missing or a hex value is invalid.
        """

    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension for this target (e.g. '.ghostty')."""

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _validate_hex(key: str, value: str) -> None:
        """Raise ValueError if value is not a valid #RRGGBB hex string."""
        if (
            not value.startswith("#")
            or len(value) != 7
            or not all(c in "0123456789abcdefABCDEF" for c in value[1:])
        ):
            raise ValueError(f"Invalid hex color for {key!r}: {value!r}")
