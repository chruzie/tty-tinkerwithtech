"""Prompt mode pipeline — sanitize → cache → LLM → validate → cache."""

from __future__ import annotations

import hashlib

from cache.db import ThemeRepository
from generator.llm import LLMClient, LLMError
from generator.prompt import build_prompt
from generator.serializers.ghostty import GhosttySerializer
from generator.serializers.iterm2 import ITerm2Serializer
from generator.validator import validate_theme
from security.input_sanitizer import sanitize_prompt

_SERIALIZERS = {
    "ghostty": GhosttySerializer(),
    "iterm2": ITerm2Serializer(),
}
_CACHE_SERIALIZER = GhosttySerializer()  # canonical on-disk format

_MAX_RETRIES = 3
_SPEND_CAP_USD = 1.0  # daily cap default


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_from_prompt(
    query: str,
    provider: object | None = None,
    target: str = "ghostty",
    repo: ThemeRepository | None = None,
    skip_cache: bool = False,
) -> tuple[str, int]:
    """Run the full prompt-mode pipeline.

    Returns:
        Tuple of (serialized theme string in the requested *target* format, tier).
        tier=1 for exact hash hit, tier=2 for similarity hit, tier=3 for LLM generation.

    Raises:
        ValueError: if the query is empty after sanitization.
        RuntimeError: if LLM generation fails after max retries.
    """
    if repo is None:
        repo = ThemeRepository()
        repo.init_db()

    serializer = _SERIALIZERS.get(target, _SERIALIZERS["ghostty"])

    # A1-A2: Sanitize and hash
    clean_query = sanitize_prompt(query)
    if not clean_query:
        raise ValueError("Query is empty after sanitization")

    query_hash = _hash(clean_query)

    # A3: Exact cache hit (tier 1)
    if not skip_cache:
        cached = repo.get_by_hash(query_hash)
        if cached:
            palette = validate_theme(cached["theme_data"])
            return serializer.serialize(palette), 1

    # A4: Similarity search (tier 2) — requires embeddings module
    if not skip_cache:
        try:
            from cache.embeddings import find_similar

            candidates = repo.get_all_embeddings()
            similar_id = find_similar(clean_query, candidates)
            if similar_id is not None:
                row = repo.get_by_id(similar_id)
                if row:
                    palette = validate_theme(row["theme_data"])
                    return serializer.serialize(palette), 2
        except (ImportError, RuntimeError):
            pass  # sentence-transformers not installed, skip tier 2

    # A5-A6: LLM generation with retries
    if provider is None:
        from providers.registry import resolve_provider

        provider = resolve_provider()

    # Check daily spend cap
    if repo.get_daily_spend() >= _SPEND_CAP_USD:
        raise RuntimeError(
            f"Daily spend cap of ${_SPEND_CAP_USD:.2f} reached. "
            "Use a local provider or increase the cap."
        )

    client = LLMClient()
    prompt = build_prompt(clean_query)
    theme_str: str | None = None
    palette: dict[str, str] = {}
    last_error: Exception | None = None

    tokens_used = 0
    for attempt in range(_MAX_RETRIES):
        try:
            raw, tokens_used = client.generate(prompt, provider)
            palette = validate_theme(raw)
            theme_str = serializer.serialize(palette)
            break
        except (LLMError, ValueError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES - 1:
                continue

    if theme_str is None:
        raise RuntimeError(
            f"Theme generation failed after {_MAX_RETRIES} attempts: {last_error}"
        )

    # A7: Embed and cache result
    embedding: list[float] | None = None
    try:
        from cache.embeddings import embed

        embedding = embed(clean_query)
    except (ImportError, RuntimeError):
        pass

    # Cache always stores Ghostty format (canonical) so validate_theme can re-parse
    # on future cache hits regardless of what target was requested.
    cached_data = _CACHE_SERIALIZER.serialize(palette)
    cost = getattr(provider, "cost_per_1k_tokens", 0.0) * (tokens_used / 1000)
    repo.save_theme(
        query_hash=query_hash,
        theme_data=cached_data,
        input_type="prompt",
        query_raw=clean_query,
        embedding=embedding,
        provider=getattr(provider, "name", "unknown"),
        cost_usd=cost,
    )
    if cost > 0 and hasattr(provider, "name"):
        repo.log_cost(provider.name, cost)

    return theme_str, 3
