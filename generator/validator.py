"""Theme validator — schema completeness + WCAG AA contrast check."""

from __future__ import annotations

from generator.serializers.base import REQUIRED_KEYS

_HEX_CHARS = frozenset("0123456789abcdefABCDEF")


def _is_valid_hex(value: str) -> bool:
    return (
        value.startswith("#")
        and len(value) == 7
        and all(c in _HEX_CHARS for c in value[1:])
    )


def _relative_luminance(hex_color: str) -> float:
    """Return WCAG relative luminance for a #RRGGBB color."""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linearized = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * linearized[0] + 0.7152 * linearized[1] + 0.0722 * linearized[2]


def contrast_ratio(fg: str, bg: str) -> float:
    """Return WCAG contrast ratio between two #RRGGBB hex colors."""
    lum_fg = _relative_luminance(fg)
    lum_bg = _relative_luminance(bg)
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    return (lighter + 0.05) / (darker + 0.05)


def validate_theme(theme_str: str) -> dict[str, str]:
    """Parse and validate a Ghostty key=value theme string.

    Returns:
        A dict mapping each key to its hex value.

    Raises:
        ValueError: on missing keys, invalid hex, or insufficient contrast.
    """
    palette: dict[str, str] = {}

    for line in theme_str.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Handle both "palette = 0 = #hex" and "background = #hex"
        if line.startswith("palette = "):
            # "palette = 0 = #hex"
            parts = line.split("=", 2)
            if len(parts) != 3:  # noqa: PLR2004
                raise ValueError(f"Cannot parse line: {line!r}")
            key = (parts[0] + "= " + parts[1].strip()).rstrip()
            # Normalise to "palette = N"
            key = "palette = " + parts[1].strip()
            value = parts[2].strip()
        else:
            parts = line.split("=", 1)
            if len(parts) != 2:  # noqa: PLR2004
                raise ValueError(f"Cannot parse line: {line!r}")
            key = parts[0].strip()
            value = parts[1].strip()

        if not _is_valid_hex(value):
            raise ValueError(f"Invalid hex color for {key!r}: {value!r}")

        palette[key] = value

    missing = REQUIRED_KEYS - palette.keys()
    if missing:
        raise ValueError(f"Missing required theme keys: {sorted(missing)}")

    # WCAG AA: foreground/background contrast >= 4.5:1
    ratio = contrast_ratio(palette["foreground"], palette["background"])
    if ratio < 4.5:  # noqa: PLR2004
        raise ValueError(
            f"Insufficient contrast ratio {ratio:.2f}:1 (minimum 4.5:1 WCAG AA)"
        )

    return palette
