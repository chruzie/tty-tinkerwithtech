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
