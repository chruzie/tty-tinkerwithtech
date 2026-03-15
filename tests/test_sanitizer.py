"""Tests for security/input_sanitizer.py."""

from __future__ import annotations

import warnings

from security.input_sanitizer import sanitize_prompt


def test_basic_passthrough() -> None:
    assert sanitize_prompt("cyberpunk neon rain") == "cyberpunk neon rain"


def test_strip_whitespace() -> None:
    assert sanitize_prompt("  hello   world  ") == "hello world"


def test_collapse_internal_whitespace() -> None:
    assert sanitize_prompt("foo\t\tbar\n\nbaz") == "foo bar baz"


def test_nfkc_normalization_ligature() -> None:
    # LATIN SMALL LIGATURE FF (U+FB00) → "ff"
    result = sanitize_prompt("\ufb00oo")
    assert result == "ffoo"


def test_homoglyph_normalization() -> None:
    # Fullwidth latin A (U+FF21) → A
    result = sanitize_prompt("\uff21BC")
    assert result == "ABC"


def test_truncation_at_200_bytes() -> None:
    long_text = "a" * 250
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = sanitize_prompt(long_text)
    assert len(result.encode("utf-8")) <= 200
    assert len(w) == 1
    assert "truncated" in str(w[0].message).lower()


def test_multibyte_truncation_safe() -> None:
    # 3-byte chars: 67 × 3 = 201 bytes → must truncate cleanly
    text = "\u4e2d" * 70  # CJK character, 3 bytes each
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = sanitize_prompt(text)
    # Result must be valid UTF-8 and <= 200 bytes
    assert len(result.encode("utf-8")) <= 200
    result.encode("utf-8")  # must not raise
