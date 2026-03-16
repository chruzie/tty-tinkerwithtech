"""Prompt input sanitizer — NFKC normalization, length cap, unicode safety."""

from __future__ import annotations

import re
import unicodedata

_MAX_CHARS = 200
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_control_chars(text: str) -> str:
    """Remove Unicode control characters (Cc, Cf) except tab, newline, carriage return."""
    return "".join(
        ch
        for ch in text
        if unicodedata.category(ch) not in ("Cc", "Cf") or ch in ("\t", "\n", "\r")
    )


def sanitize_prompt(text: str) -> str:
    """Sanitize and normalize a user prompt string.

    Steps:
    1. Strip ASCII/Unicode control characters (Cc, Cf) to prevent log injection.
    2. NFKC unicode normalization (homoglyphs, ligatures, etc.)
    3. Strip leading/trailing whitespace; collapse internal whitespace.
    4. Raise ValueError('prompt_too_long') if len > 200 characters.

    Returns:
        Cleaned string.

    Raises:
        ValueError: if the input is empty after normalization.
        ValueError: 'prompt_too_long' if the stripped input exceeds 200 characters.
    """
    # Step 1: Strip control characters
    text = _strip_control_chars(text)

    # Step 2: NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # Step 3: Collapse whitespace
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()

    # Step 4: Raise if empty after sanitization
    if not normalized:
        raise ValueError("Prompt is empty after sanitization")

    # Step 5: Raise if too long
    if len(normalized) > _MAX_CHARS:
        raise ValueError("prompt_too_long")

    return normalized
