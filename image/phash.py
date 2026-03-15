"""Perceptual hash for image-mode cache keying."""

from __future__ import annotations

from PIL import Image


def compute_phash(img: Image.Image) -> str:
    """Return a hex string perceptual hash for *img*.

    Uses imagehash.phash (64-bit dHash variant). Two near-identical images
    produce hashes with Hamming distance < 10.
    """
    import imagehash

    h = imagehash.phash(img)
    return str(h)


def phash_distance(h1: str, h2: str) -> int:
    """Return the Hamming distance between two hex phash strings."""
    import imagehash

    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
