"""Tests for security/input_sanitizer.py."""

from __future__ import annotations

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


def test_over_200_chars_raises() -> None:
    import pytest

    long_text = "a" * 201
    with pytest.raises(ValueError, match="prompt_too_long"):
        sanitize_prompt(long_text)


def test_exactly_200_chars_ok() -> None:
    text = "a" * 200
    assert sanitize_prompt(text) == text
