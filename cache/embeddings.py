"""MiniLM local embeddings + cosine similarity for tier-2 cache lookups.

sentence-transformers is an optional dependency. Install it with:
    uv sync --extra embeddings
"""

from __future__ import annotations

import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # Loaded lazily


def _get_model():  # type: ignore[no-untyped-def]
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Install tty-theme[embeddings] to enable similarity search: "
                "uv sync --extra embeddings"
            ) from exc
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
    candidates: list[tuple[int | str, list[float]]],
    threshold: float = 0.85,
) -> int | str | None:
    """Return the theme id of the most similar cached embedding, or None.

    Args:
        query: the raw query string to embed and compare.
        candidates: list of (theme_id, embedding_vector) from the cache.
            theme_id is int for SQLite repos and str for Firestore repos.
        threshold: minimum cosine similarity to count as a match.
    """
    if not candidates:
        return None

    ids = [c[0] for c in candidates]
    matrix = np.array([c[1] for c in candidates], dtype=np.float32)  # (N, D)
    query_vec = np.array(embed(query), dtype=np.float32)              # (D,)

    norms = np.linalg.norm(matrix, axis=1)                           # (N,)
    query_norm = float(np.linalg.norm(query_vec))

    denom = norms * query_norm
    # Avoid division by zero for zero-length vectors
    denom = np.where(denom == 0.0, 1.0, denom)

    scores = (matrix @ query_vec) / denom                            # (N,)
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    return ids[best_idx] if best_score >= threshold else None
