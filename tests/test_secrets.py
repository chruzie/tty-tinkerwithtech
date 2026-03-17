"""Tests for security/secrets.py — get_secret name validation."""

from __future__ import annotations

import pytest

from security.secrets import get_secret


def test_invalid_name_path_traversal() -> None:
    with pytest.raises(ValueError, match="Invalid secret name"):
        get_secret("../../bad")


def test_invalid_name_lowercase() -> None:
    with pytest.raises(ValueError, match="Invalid secret name"):
        get_secret("my_secret")


def test_invalid_name_starts_with_digit() -> None:
    with pytest.raises(ValueError, match="Invalid secret name"):
        get_secret("1SECRET")


def test_invalid_name_empty() -> None:
    with pytest.raises(ValueError, match="Invalid secret name"):
        get_secret("")


def test_invalid_name_with_slash() -> None:
    with pytest.raises(ValueError, match="Invalid secret name"):
        get_secret("SECRET/KEY")


def test_valid_name_raises_key_error_when_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(KeyError):
        get_secret("GEMINI_API_KEY")


def test_valid_name_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MY_TEST_SECRET", "hunter2")
    result = get_secret("MY_TEST_SECRET")
    assert result == "hunter2"


def test_valid_name_with_leading_underscore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("_PRIVATE_KEY", "val")
    result = get_secret("_PRIVATE_KEY")
    assert result == "val"
