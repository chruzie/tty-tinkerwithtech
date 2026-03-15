"""Safe image loader — magic bytes, size cap, EXIF strip."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB

_ALLOWED_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}


def _check_magic(data: bytes) -> None:
    """Reject files whose magic bytes don't match a supported image type."""
    # JPEG: starts with FF D8 FF
    if data[:3] == b"\xff\xd8\xff":
        return
    # PNG: starts with 89 50 4E 47
    if data[:4] == b"\x89PNG":
        return
    # GIF: starts with GIF8
    if data[:4] == b"GIF8":
        return
    # WebP: RIFF container AND bytes 8-11 == WEBP (rejects WAV and other RIFF types)
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # noqa: PLR2004
        return
    raise ValueError("File is not a recognised image format (magic bytes check failed)")


def load_image(source: str | Path) -> Image.Image:
    """Load an image from a local path or HTTPS URL.

    Performs:
    - SSRF guard (HTTPS only, no RFC1918)
    - Magic byte validation
    - 20 MB size cap
    - PIL format allowlist (JPEG/PNG/GIF/WEBP)
    - EXIF metadata strip

    Returns:
        A PIL Image in RGB mode.
    """
    if isinstance(source, Path) or (isinstance(source, str) and not source.startswith("http")):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        data = path.read_bytes()
    else:
        from security.ssrf_guard import safe_fetch

        resp = safe_fetch(str(source), timeout=30.0, follow_redirects=False)
        resp.raise_for_status()
        data = resp.content

    if len(data) > _MAX_BYTES:
        raise ValueError(f"Image exceeds size cap ({len(data)} > {_MAX_BYTES} bytes)")

    _check_magic(data)

    import io

    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported or corrupt image format") from exc

    if img.format not in _ALLOWED_FORMATS:
        raise ValueError(f"Unsupported image format: {img.format}")

    # Strip EXIF by converting through raw pixel data
    img_clean = Image.new(img.mode, img.size)
    img_clean.putdata(list(img.getdata()))

    return img_clean.convert("RGB")
