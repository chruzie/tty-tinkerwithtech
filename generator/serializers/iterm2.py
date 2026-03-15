"""iTerm2 XML plist (.itermcolors) theme serializer."""

from __future__ import annotations

from generator.serializers.base import REQUIRED_KEYS, ThemeSerializer

# Mapping of iTerm2 key names → Ghostty palette keys
_ANSI_MAP: list[tuple[str, str]] = [
    (f"Ansi {i} Color", f"palette = {i}") for i in range(16)
]
_SEMANTIC_MAP: list[tuple[str, str]] = [
    ("Background Color", "background"),
    ("Foreground Color", "foreground"),
    ("Cursor Color", "cursor-color"),
    ("Selection Color", "selection-background"),
    ("Selected Text Color", "selection-foreground"),
    # Bold Color → palette 15 (bright white)
    ("Bold Color", "palette = 15"),
    # Cursor Text Color → background
    ("Cursor Text Color", "background"),
    # Link Color → palette 4 (blue)
    ("Link Color", "palette = 4"),
]
_ALL_MAP = _ANSI_MAP + _SEMANTIC_MAP

_XML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
    '  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n'
)


def _hex_to_components(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB → (r, g, b) floats in [0, 1]."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return r, g, b


class ITerm2Serializer(ThemeSerializer):
    """Serialize a palette dict to iTerm2 XML plist format."""

    def serialize(self, palette: dict[str, str]) -> str:
        missing = REQUIRED_KEYS - palette.keys()
        if missing:
            raise ValueError(f"Missing required theme keys: {sorted(missing)}")

        for key, value in palette.items():
            if key in REQUIRED_KEYS:
                self._validate_hex(key, value)

        lines: list[str] = [_XML_HEADER, "<dict>\n"]

        for iterm_key, ghostty_key in _ALL_MAP:
            hex_color = palette[ghostty_key]
            r, g, b = _hex_to_components(hex_color)
            lines.append(f"  <key>{iterm_key}</key>\n")
            lines.append("  <dict>\n")
            lines.append("    <key>Alpha Component</key><real>1</real>\n")
            lines.append(f"    <key>Blue Component</key><real>{b:.6f}</real>\n")
            lines.append("    <key>Color Space</key><string>sRGB</string>\n")
            lines.append(f"    <key>Green Component</key><real>{g:.6f}</real>\n")
            lines.append(f"    <key>Red Component</key><real>{r:.6f}</real>\n")
            lines.append("  </dict>\n")

        lines.append("</dict>\n")
        lines.append("</plist>\n")
        return "".join(lines)

    def file_extension(self) -> str:
        return ".itermcolors"
