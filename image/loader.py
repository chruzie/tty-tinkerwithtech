"""Safe image loader — magic bytes, size cap, EXIF strip."""

from __future__ import annotations

from pathlib import Path

import httpx
from PIL import Image

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG": "png",
    b"GIF8": "gif",
    b"RIFF": "webp",  # RIFF....WEBP
    b"\x00\x00\x00": "mp4/heif",  # broad match, filtered later by PIL
}

_ALLOWED_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}


def _check_magic(data: bytes) -> None:
    for magic, _fmt in _ALLOWED_MAGIC.items():
        if data[: len(magic)] == magic:
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
        from security.ssrf_guard import check_url

        check_url(str(source))
        resp = httpx.get(str(source), timeout=30.0, follow_redirects=False)
        resp.raise_for_status()
        data = resp.content

    if len(data) > _MAX_BYTES:
        raise ValueError(f"Image exceeds size cap ({len(data)} > {_MAX_BYTES} bytes)")

    _check_magic(data)

    import io

    img = Image.open(io.BytesIO(data))

    if img.format not in _ALLOWED_FORMATS:
        raise ValueError(f"Unsupported image format: {img.format}")

    # Strip EXIF by converting through raw pixel data
    img_clean = Image.new(img.mode, img.size)
    img_clean.putdata(list(img.getdata()))

    return img_clean.convert("RGB")
