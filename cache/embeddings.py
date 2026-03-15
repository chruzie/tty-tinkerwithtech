"""MiniLM local embeddings + cosine similarity for tier-2 cache lookups."""

from __future__ import annotations

import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # Loaded lazily


def _get_model():  # type: ignore[no-untyped-def]
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(text: str) -> list[float]:
    """Return a normalized embedding vector for *text*."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity in [-1, 1] between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def find_similar(
    query: str,
    candidates: list[tuple[int, list[float]]],
    threshold: float = 0.85,
) -> int | None:
    """Return the theme id of the most similar cached embedding, or None.

    Args:
        query: the raw query string to embed and compare.
        candidates: list of (theme_id, embedding_vector) from the cache.
        threshold: minimum cosine similarity to count as a match.
    """
    if not candidates:
        return None

    query_vec = embed(query)
    best_id = None
    best_score = -1.0

    for theme_id, vec in candidates:
        score = cosine_similarity(query_vec, vec)
        if score > best_score:
            best_score = score
            best_id = theme_id

    return best_id if best_score >= threshold else None
