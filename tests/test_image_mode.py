"""Tests for modes/image_mode.py — focused on the refine prompt fix."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

_VALID_THEME = (
    "\n".join(f"palette = {i} = #{'ab' * 3}" for i in range(16))
    + "\nbackground = #0a0a0a\nforeground = #f0f0f0\ncursor-color = #f0f0f0"
    "\nselection-background = #1a1a1a\nselection-foreground = #f0f0f0"
)

_FAKE_COLORS = [f"#{i:02x}{i:02x}{i:02x}" for i in range(16)]


def _fake_image():
    """Return a small PIL RGBA image for testing."""
    from PIL import Image

    return Image.new("RGB", (10, 10), color=(100, 100, 100))


def test_refine_uses_build_refine_prompt():
    """BUG-06: image refine path must call build_refine_prompt, not build_prompt."""

    from modes.image_mode import generate_from_image

    mock_provider = MagicMock()
    mock_provider.name = "mock"
    mock_provider.generate.return_value = _VALID_THEME

    with (
        tempfile.TemporaryDirectory() as d,
        patch("modes.image_mode.load_image", return_value=_fake_image()),
        patch("modes.image_mode.compute_phash", return_value="abc123"),
        patch("modes.image_mode.extract_palette", return_value=_FAKE_COLORS),
        patch("modes.image_mode.map_to_theme", return_value={
            **{f"palette = {i}": f"#{'ab' * 3}" for i in range(16)},
            "background": "#0a0a0a",
            "foreground": "#f0f0f0",
            "cursor-color": "#f0f0f0",
            "selection-background": "#1a1a1a",
            "selection-foreground": "#f0f0f0",
        }),
        patch("generator.prompt.build_prompt") as mock_build_prompt,
        patch("generator.prompt.build_refine_prompt", return_value={"system": "Refine the base palette", "user": "colors"}) as mock_refine_prompt,
    ):
        from cache.db import ThemeRepository

        repo = ThemeRepository(db_path=Path(d) / "test.db")
        repo.init_db()

        generate_from_image(
            "https://example.com/img.jpg",
            refine=True,
            provider=mock_provider,
            repo=repo,
        )

    # build_refine_prompt should have been called, build_prompt should NOT
    mock_refine_prompt.assert_called_once()
    mock_build_prompt.assert_not_called()

    # The system key of the prompt passed to provider.generate must contain refine text
    called_prompt = mock_provider.generate.call_args[0][0]
    assert "Refine" in called_prompt["system"]


def test_extract_palette_accepts_rgba():
    """extract_palette must handle RGBA images without crashing (BUG-05)."""
    from PIL import Image

    from image.extractor import extract_palette

    rgba_img = Image.new("RGBA", (10, 10), color=(100, 150, 200, 128))
    colors = extract_palette(rgba_img, n_colors=2)
    assert len(colors) == 2
    assert all(c.startswith("#") for c in colors)


def test_extract_palette_accepts_grayscale():
    """extract_palette must handle L-mode (grayscale) images."""
    from PIL import Image

    from image.extractor import extract_palette

    gray_img = Image.new("L", (10, 10), color=128)
    colors = extract_palette(gray_img, n_colors=2)
    assert len(colors) == 2
