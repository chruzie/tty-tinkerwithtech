"""Image mode pipeline — load → pHash → cache → k-means → map → validate → cache."""

from __future__ import annotations

from pathlib import Path

from cache.db import ThemeRepository
from generator.serializers.ghostty import GhosttySerializer
from generator.serializers.iterm2 import ITerm2Serializer
from generator.validator import validate_theme
from image.extractor import extract_palette
from image.loader import load_image
from image.palette_mapper import map_to_theme
from image.phash import compute_phash

_SERIALIZERS = {
    "ghostty": GhosttySerializer(),
    "iterm2": ITerm2Serializer(),
}


def generate_from_image(
    source: str | Path,
    target: str = "ghostty",
    refine: bool = False,
    provider: object | None = None,
    repo: ThemeRepository | None = None,
    skip_cache: bool = False,
) -> str:
    """Run the full image-mode pipeline.

    Args:
        source: local file path or HTTPS URL.
        target: output format ('ghostty' or 'iterm2').
        refine: if True, pass the extracted palette through LLM refinement.
        provider: LLM provider (only used when refine=True).
        repo: optional injected repository (for testing).
        skip_cache: bypass cache lookup.

    Returns:
        Serialized theme string in the requested *target* format.
    """
    if repo is None:
        repo = ThemeRepository()
        repo.init_db()

    serializer = _SERIALIZERS.get(target, _SERIALIZERS["ghostty"])

    # B1: Load and validate image
    img = load_image(source)

    # B2: Compute pHash for cache key
    phash = compute_phash(img)

    # B3: Exact pHash cache hit
    if not skip_cache:
        cached = repo.get_by_hash(phash)
        if cached:
            return cached["theme_data"]

    # B4: k-means colour extraction
    colors = extract_palette(img, n_colors=16)

    # B5: Map to theme dict
    palette_dict = map_to_theme(colors)

    if refine and provider is not None:
        # B6: Optional LLM refinement pass
        from generator.llm import LLMClient, LLMError
        from generator.prompt import build_prompt

        palette_str = "\n".join(f"{k} = {v}" for k, v in palette_dict.items())
        prompt = build_prompt(f"Refine this extracted palette:\n{palette_str}")
        client = LLMClient()
        try:
            raw = client.generate(prompt, provider)
            palette_dict = validate_theme(raw)
        except (LLMError, ValueError):
            pass  # Fall back to the extracted palette on failure

    # B7: Validate final palette
    palette_str = "\n".join(f"{k} = {v}" for k, v in palette_dict.items())
    validated = validate_theme(palette_str)
    theme_str = serializer.serialize(validated)

    # B8: Cache result
    repo.save_theme(
        query_hash=phash,
        theme_data=theme_str,
        input_type="image",
        source="image",
        provider=getattr(provider, "name", None) if refine else None,
    )

    return theme_str
