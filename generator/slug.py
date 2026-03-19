"""URL-safe slug generation for theme names."""

from __future__ import annotations

import re


def make_slug(name: str) -> str:
    """Convert a theme name to a URL-safe slug.

    Steps:
    1. Lowercase.
    2. Replace spaces and underscores with hyphens.
    3. Strip non-alphanumeric characters except hyphens.
    4. Collapse consecutive hyphens.
    5. Strip leading/trailing hyphens.

    Examples:
        make_slug('Tokyo Midnight!') == 'tokyo-midnight'
        make_slug('  --neon rain-- ') == 'neon-rain'
    """
    slug = name.lower()
    slug = re.sub(r"[ _]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug
