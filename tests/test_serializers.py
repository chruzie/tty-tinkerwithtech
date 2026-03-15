"""Tests for Ghostty and iTerm2 serializers."""

from __future__ import annotations

import pytest

from generator.serializers.ghostty import GhosttySerializer
from generator.serializers.iterm2 import ITerm2Serializer

_FULL_PALETTE: dict[str, str] = {
    "palette = 0": "#1a1a2e",
    "palette = 1": "#e63946",
    "palette = 2": "#57cc99",
    "palette = 3": "#f4a261",
    "palette = 4": "#4895ef",
    "palette = 5": "#b5179e",
    "palette = 6": "#4cc9f0",
    "palette = 7": "#ced4da",
    "palette = 8": "#6c757d",
    "palette = 9": "#ff6b6b",
    "palette = 10": "#80ffdb",
    "palette = 11": "#ffd166",
    "palette = 12": "#74b9ff",
    "palette = 13": "#d63af9",
    "palette = 14": "#00f5d4",
    "palette = 15": "#ffffff",
    "background": "#1a1a2e",
    "foreground": "#ced4da",
    "cursor-color": "#f4a261",
    "selection-background": "#4895ef",
    "selection-foreground": "#1a1a2e",
}


class TestGhosttySerializer:
    def test_serialize_full_palette(self) -> None:
        s = GhosttySerializer()
        result = s.serialize(_FULL_PALETTE)
        lines = result.strip().splitlines()
        assert len(lines) == 21
        assert lines[0] == "palette = 0 = #1a1a2e"
        assert "background = #1a1a2e" in result

    def test_file_extension(self) -> None:
        assert GhosttySerializer().file_extension() == ".ghostty"

    def test_missing_key_raises(self) -> None:
        bad = {k: v for k, v in _FULL_PALETTE.items() if k != "background"}
        with pytest.raises(ValueError, match="Missing required theme keys"):
            GhosttySerializer().serialize(bad)

    def test_invalid_hex_raises(self) -> None:
        bad = {**_FULL_PALETTE, "background": "not-a-color"}
        with pytest.raises(ValueError, match="Invalid hex color"):
            GhosttySerializer().serialize(bad)

    def test_roundtrip_all_keys_present(self) -> None:
        result = GhosttySerializer().serialize(_FULL_PALETTE)
        for key in _FULL_PALETTE:
            assert key in result


class TestITerm2Serializer:
    def test_file_extension(self) -> None:
        assert ITerm2Serializer().file_extension() == ".itermcolors"

    def test_serialize_produces_valid_xml(self) -> None:
        result = ITerm2Serializer().serialize(_FULL_PALETTE)
        assert result.startswith("<?xml")
        assert "<plist" in result
        assert "</plist>" in result

    def test_hex_conversion_1a1a2e(self) -> None:
        """#1a1a2e → R=0.101961 G=0.101961 B=0.180392"""
        result = ITerm2Serializer().serialize(_FULL_PALETTE)
        # background is #1a1a2e — check red component
        assert "0.101961" in result

    def test_all_iterm2_keys_present(self) -> None:
        result = ITerm2Serializer().serialize(_FULL_PALETTE)
        for expected in [
            "Ansi 0 Color", "Ansi 15 Color",
            "Background Color", "Foreground Color",
            "Bold Color", "Cursor Color", "Cursor Text Color",
            "Selection Color", "Selected Text Color", "Link Color",
        ]:
            assert expected in result, f"Missing key: {expected}"

    def test_missing_key_raises(self) -> None:
        bad = {k: v for k, v in _FULL_PALETTE.items() if k != "foreground"}
        with pytest.raises(ValueError, match="Missing required theme keys"):
            ITerm2Serializer().serialize(bad)

    def test_color_space_is_srgb(self) -> None:
        result = ITerm2Serializer().serialize(_FULL_PALETTE)
        assert result.count("<string>sRGB</string>") == 24  # one per color entry
