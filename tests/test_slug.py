"""Tests for generator/slug.py."""

from __future__ import annotations

from generator.slug import make_slug


def test_basic_slug() -> None:
    assert make_slug("Tokyo Midnight!") == "tokyo-midnight"


def test_leading_trailing_hyphens() -> None:
    assert make_slug("  --neon rain-- ") == "neon-rain"


def test_underscore_to_hyphen() -> None:
    assert make_slug("cyber_punk") == "cyber-punk"


def test_consecutive_spaces() -> None:
    assert make_slug("a   b") == "a-b"


def test_special_chars_stripped() -> None:
    assert make_slug("hello@world!") == "helloworld"


def test_already_slug() -> None:
    assert make_slug("ocean-breeze") == "ocean-breeze"
