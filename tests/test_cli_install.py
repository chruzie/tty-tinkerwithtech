"""Tests for _install_theme path-traversal guard (US-003)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cli.main import _install_theme


def _mock_dir(tmp_path):
    """Return a patcher that redirects _GHOSTTY_THEMES to tmp_path."""
    import cli.main as m

    return patch.object(m, "_GHOSTTY_THEMES", tmp_path)


@pytest.mark.parametrize(
    "bad_name",
    [
        "../../evil",
        "../evil",
        "/etc/passwd",
        ".hidden",
        "-leading-dash",
        "has/slash",
        "",
    ],
)
def test_install_rejects_bad_names(bad_name, tmp_path):
    with _mock_dir(tmp_path):
        with pytest.raises(ValueError, match="Invalid theme name"):
            _install_theme(bad_name, "content", "ghostty")


def test_install_accepts_valid_name(tmp_path):
    with _mock_dir(tmp_path):
        dest = _install_theme("my-theme", "content", "ghostty")
    assert dest.name == "my-theme"
    assert dest.read_text() == "content"


def test_install_accepts_name_with_spaces(tmp_path):
    """Spaces are replaced with hyphens before validation."""
    with _mock_dir(tmp_path):
        dest = _install_theme("My Cool Theme", "data", "ghostty")
    assert dest.name == "my-cool-theme"


def test_install_rejects_dotdot_after_normalise(tmp_path):
    """../../evil after lower() should still be rejected."""
    with _mock_dir(tmp_path):
        with pytest.raises(ValueError, match="Invalid theme name"):
            _install_theme("../../Evil", "data", "ghostty")


def test_install_returns_none_if_exists_without_force(tmp_path):
    """Overwrite guard: returns None and does not overwrite when file exists."""
    with _mock_dir(tmp_path):
        dest = _install_theme("my-theme", "original", "ghostty")
        assert dest is not None
        result = _install_theme("my-theme", "new-content", "ghostty", force=False)
    assert result is None
    assert dest.read_text() == "original"  # file not overwritten


def test_install_overwrites_with_force(tmp_path):
    """--force allows overwrite of an existing theme."""
    with _mock_dir(tmp_path):
        _install_theme("my-theme", "original", "ghostty")
        dest = _install_theme("my-theme", "updated", "ghostty", force=True)
    assert dest is not None
    assert dest.read_text() == "updated"
