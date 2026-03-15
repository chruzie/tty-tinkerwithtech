"""Tests for generator/validator.py."""

from __future__ import annotations

import pytest

from generator.validator import contrast_ratio, validate_theme

_VALID_THEME = """\
palette = 0 = #1a1a2e
palette = 1 = #e63946
palette = 2 = #57cc99
palette = 3 = #f4a261
palette = 4 = #4895ef
palette = 5 = #b5179e
palette = 6 = #4cc9f0
palette = 7 = #ced4da
palette = 8 = #6c757d
palette = 9 = #ff6b6b
palette = 10 = #80ffdb
palette = 11 = #ffd166
palette = 12 = #74b9ff
palette = 13 = #d63af9
palette = 14 = #00f5d4
palette = 15 = #ffffff
background = #1a1a2e
foreground = #ced4da
cursor-color = #f4a261
selection-background = #4895ef
selection-foreground = #1a1a2e
"""


def test_valid_theme_parses() -> None:
    result = validate_theme(_VALID_THEME)
    assert result["background"] == "#1a1a2e"
    assert result["foreground"] == "#ced4da"
    assert len(result) == 21


def test_missing_key_raises() -> None:
    # Drop background line
    broken = "\n".join(
        line for line in _VALID_THEME.splitlines() if not line.startswith("background")
    )
    with pytest.raises(ValueError, match="Missing required theme keys"):
        validate_theme(broken)


def test_invalid_hex_raises() -> None:
    broken = _VALID_THEME.replace("background = #1a1a2e", "background = notahex")
    with pytest.raises(ValueError, match="Invalid hex color"):
        validate_theme(broken)


def test_low_contrast_raises() -> None:
    # Dark fg on dark bg → low contrast
    broken = _VALID_THEME.replace("foreground = #ced4da", "foreground = #1b1b2f")
    with pytest.raises(ValueError, match="Insufficient contrast"):
        validate_theme(broken)


def test_contrast_ratio_same_color() -> None:
    assert contrast_ratio("#000000", "#000000") == pytest.approx(1.0)


def test_contrast_ratio_black_white() -> None:
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.1)
