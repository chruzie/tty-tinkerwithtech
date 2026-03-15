"""Map extracted image colours to the Ghostty/iTerm2 key schema."""

from __future__ import annotations


def map_to_theme(colors: list[str]) -> dict[str, str]:
    """Map a sorted (dark→bright) list of hex colours to theme keys.

    Expects at least 16 colours; extra colours are ignored.

    Returns:
        A dict with all 21 required theme keys.
    """
    if len(colors) < 16:  # noqa: PLR2004
        raise ValueError(f"Need at least 16 colours, got {len(colors)}")

    # ANSI palette: 0-7 normal, 8-15 bright
    palette = {f"palette = {i}": colors[i] for i in range(16)}

    # Semantic keys derived from the palette
    darkest = colors[0]
    dark2 = colors[1] if len(colors) > 1 else colors[0]
    brightest = colors[15]
    bright_mid = colors[12] if len(colors) > 12 else colors[14]

    semantic = {
        "background": darkest,
        "foreground": brightest,
        "cursor-color": bright_mid,
        "selection-background": dark2,
        "selection-foreground": brightest,
    }

    return {**palette, **semantic}
