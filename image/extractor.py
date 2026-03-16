"""k-means colour extractor — extract dominant colours from an image."""

from __future__ import annotations

import numpy as np
from PIL import Image
from sklearn.cluster import MiniBatchKMeans


def extract_palette(img: Image.Image, n_colors: int = 16) -> list[str]:
    """Extract *n_colors* dominant colours from *img* using k-means.

    Returns:
        List of ``#RRGGBB`` hex strings, sorted dark → bright.
    """
    # Ensure RGB so reshape(-1, 3) is always valid (handles RGBA, L, P, etc.)
    img = img.convert("RGB")
    # Downsample for speed
    img_small = img.resize((150, 150), Image.LANCZOS)
    pixels = np.array(img_small).reshape(-1, 3).astype(np.float32)

    kmeans = MiniBatchKMeans(
        n_clusters=n_colors,
        n_init=3,
        random_state=42,
        max_iter=100,
    )
    kmeans.fit(pixels)
    centers = kmeans.cluster_centers_.astype(int)

    # Sort by perceived brightness (luminance)
    def _luminance(rgb: np.ndarray) -> float:
        r, g, b = rgb / 255.0
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    centers_sorted = sorted(centers, key=_luminance)
    return [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for r, g, b in centers_sorted]
