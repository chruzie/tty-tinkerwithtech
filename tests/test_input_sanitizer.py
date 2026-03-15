"""Tests for security/input_sanitizer.py — sanitize_prompt."""

from __future__ import annotations

import pytest

from security.input_sanitizer import sanitize_prompt


def test_empty_string_raises() -> None:
    with pytest.raises(ValueError, match="empty after sanitization"):
        sanitize_prompt("")


def test_only_whitespace_raises() -> None:
    with pytest.raises(ValueError, match="empty after sanitization"):
        sanitize_prompt("   \t\n  ")


def test_only_control_chars_raises() -> None:
    with pytest.raises(ValueError, match="empty after sanitization"):
        sanitize_prompt("\x00\x01\x02\x03")


def test_strip_null_and_control_chars() -> None:
    result = sanitize_prompt("\x00\x01hello")
    assert result == "hello"


def test_strip_mixed_control_chars() -> None:
    result = sanitize_prompt("cy\x02ber\x1bpunk")
    assert result == "cyberpunk"


def test_strip_unicode_format_category() -> None:
    # U+200B zero-width space (Cf category) should be stripped
    result = sanitize_prompt("hello\u200bworld")
    assert result == "helloworld"


def test_normal_prompt_unchanged() -> None:
    result = sanitize_prompt("tokyo midnight")
    assert result == "tokyo midnight"


def test_collapse_internal_whitespace() -> None:
    result = sanitize_prompt("  cyberpunk   neon  ")
    assert result == "cyberpunk neon"


def test_nfkc_normalization() -> None:
    # Ligature fi → fi (two chars)
    result = sanitize_prompt("\ufb01le")
    assert result == "file"


def test_tab_and_newline_preserved_before_collapse() -> None:
    # Tabs/newlines are allowed control chars but collapsed to a single space
    result = sanitize_prompt("hello\tworld")
    assert result == "hello world"


def test_truncation_with_warning(recwarn: pytest.WarningsChecker) -> None:
    long_prompt = "a" * 300
    result = sanitize_prompt(long_prompt)
    assert len(result.encode("utf-8")) <= 200
    assert len(recwarn) == 1
    assert "truncated" in str(recwarn[0].message).lower()
