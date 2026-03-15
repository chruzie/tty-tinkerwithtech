"""Ghostty key=value theme serializer."""

from __future__ import annotations

from generator.serializers.base import REQUIRED_KEYS, ThemeSerializer

_PALETTE_ORDER = [f"palette = {i}" for i in range(16)]
_SEMANTIC_ORDER = [
    "background",
    "foreground",
    "cursor-color",
    "selection-background",
    "selection-foreground",
]
_OUTPUT_ORDER = _PALETTE_ORDER + _SEMANTIC_ORDER


class GhosttySerializer(ThemeSerializer):
    """Serialize a palette dict to Ghostty key=value format."""

    def serialize(self, palette: dict[str, str]) -> str:
        missing = REQUIRED_KEYS - palette.keys()
        if missing:
            raise ValueError(f"Missing required theme keys: {sorted(missing)}")

        for key, value in palette.items():
            if key in REQUIRED_KEYS:
                self._validate_hex(key, value)

        lines: list[str] = []
        for key in _OUTPUT_ORDER:
            lines.append(f"{key} = {palette[key]}")

        return "\n".join(lines) + "\n"

    def file_extension(self) -> str:
        return ".ghostty"
