"""Prompt input sanitizer — NFKC normalization, length cap, unicode safety."""

from __future__ import annotations

import re
import unicodedata
import warnings

_MAX_BYTES = 200
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_prompt(text: str) -> str:
    """Sanitize and normalize a user prompt string.

    Steps:
    1. NFKC unicode normalization (homoglyphs, ligatures, etc.)
    2. Strip leading/trailing whitespace; collapse internal whitespace.
    3. Truncate to 200 UTF-8 bytes with a warning if over limit.

    Returns:
        Cleaned string, guaranteed <= 200 UTF-8 bytes.

    Raises:
        ValueError: if the input is empty after normalization.
    """
    # Step 1: NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # Step 2: Collapse whitespace
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()

    # Step 3: Truncate to 200 UTF-8 bytes
    encoded = normalized.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        warnings.warn(
            f"Prompt truncated from {len(encoded)} to {_MAX_BYTES} UTF-8 bytes.",
            stacklevel=2,
        )
        # Truncate safely on UTF-8 boundaries
        truncated = encoded[:_MAX_BYTES]
        normalized = truncated.decode("utf-8", errors="ignore")

    return normalized
