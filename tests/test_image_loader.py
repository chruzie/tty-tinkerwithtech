"""Tests for image/loader.py — magic byte validation and error handling."""

from __future__ import annotations

import struct
from unittest.mock import patch

import pytest


def _make_jpeg_header() -> bytes:
    """Minimal JPEG header."""
    return b"\xff\xd8\xff" + b"\xe0" * 17


def _make_png_header() -> bytes:
    """Minimal PNG header (enough for magic check)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _make_webp_bytes() -> bytes:
    """Minimal RIFF/WEBP container."""
    body = b"WEBP" + b"\x00" * 4
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _make_wav_bytes() -> bytes:
    """Minimal RIFF/WAV container (not WEBP)."""
    body = b"WAVE" + b"\x00" * 4
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _make_null_bytes(n: int = 20) -> bytes:
    """Binary blob starting with null bytes (no valid magic)."""
    return b"\x00" * n


def test_valid_jpeg_passes_magic():
    from image.loader import _check_magic

    _check_magic(_make_jpeg_header())  # should not raise


def test_valid_png_passes_magic():
    from image.loader import _check_magic

    _check_magic(_make_png_header())  # should not raise


def test_valid_webp_passes_magic():
    from image.loader import _check_magic

    _check_magic(_make_webp_bytes())  # should not raise


def test_wav_riff_rejected():
    """WAV files are RIFF containers but bytes 8-11 are WAVE, not WEBP — must be rejected."""
    from image.loader import _check_magic

    with pytest.raises(ValueError, match="magic bytes"):
        _check_magic(_make_wav_bytes())


def test_null_bytes_rejected():
    """Unknown binary starting with null bytes must be rejected."""
    from image.loader import _check_magic

    with pytest.raises(ValueError, match="magic bytes"):
        _check_magic(_make_null_bytes())


def test_unidentified_image_error_raises_value_error():
    """PIL.UnidentifiedImageError must be re-raised as ValueError."""
    from pathlib import Path

    from PIL import UnidentifiedImageError

    from image.loader import load_image

    # Write a fake JPEG-magic file that PIL can't actually decode
    fake_jpeg = _make_jpeg_header() + b"\x00" * 100

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=fake_jpeg),
        patch("PIL.Image.open", side_effect=UnidentifiedImageError("bad")),
    ):
        with pytest.raises(ValueError, match="Unsupported or corrupt image format"):
            load_image(Path("/fake/image.jpg"))
