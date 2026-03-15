"""Firestore-backed ThemeRepository.

Uses the same interface as ThemeRepository (cache/db.py).
Selected at runtime when FIRESTORE_PROJECT env var is set and
ENVIRONMENT != 'development'.

Local testing: set FIRESTORE_EMULATOR_HOST=localhost:8080
The google-cloud-firestore SDK automatically routes all calls to the
emulator when this env var is present — no code changes required.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any


class FirestoreThemeRepository:
    """Firestore implementation of the theme repository interface."""

    def __init__(self, project: str | None = None) -> None:
        self._project = project or os.environ.get("FIRESTORE_PROJECT", "tty-theme-local")
        self._client = None  # lazy init

    def _db(self):
        if self._client is None:
            from google.cloud import firestore  # type: ignore[import]
            self._client = firestore.Client(project=self._project)
        return self._client

    def init_db(self) -> None:
        """No-op for Firestore (collections are created on first write)."""

    # ── Write ──────────────────────────────────────────────────────────────────

    def save_theme(
        self,
        query_hash: str,
        theme_data: str,
        input_type: str,
        query_raw: str | None = None,
        name: str | None = None,
        embedding: list[float] | None = None,
        source: str = "ai",
        provider: str | None = None,
        cost_usd: float = 0.0,
    ) -> str:
        """Save a theme document; returns the Firestore document ID."""
        from google.cloud import firestore  # type: ignore[import]

        doc_ref = self._db().collection("themes").document()
        doc_ref.set({
            "query_hash": query_hash,
            "query_raw": query_raw,
            "input_type": input_type,
            "name": name,
            "theme_data": theme_data,
            # Store embedding as a plain list (Firestore native array)
            "embedding": embedding,
            "source": source,
            "provider": provider,
            "cost_usd": cost_usd,
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_by_hash(self, query_hash: str) -> dict[str, Any] | None:
        docs = (
            self._db()
            .collection("themes")
            .where("query_hash", "==", query_hash)
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None

    def get_by_id(self, theme_id: str) -> dict[str, Any] | None:  # type: ignore[override]
        doc = self._db().collection("themes").document(str(theme_id)).get()
        if doc.exists:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None

    def list_themes(self, limit: int = 100) -> list[dict[str, Any]]:
        docs = (
            self._db()
            .collection("themes")
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return result

    def get_all_embeddings(self) -> list[tuple[str, list[float]]]:
        """Return (doc_id, vector) for all themes with embeddings."""
        docs = (
            self._db()
            .collection("themes")
            .where("embedding", "!=", None)
            .stream()
        )
        result = []
        for doc in docs:
            d = doc.to_dict()
            if d.get("embedding"):
                result.append((doc.id, d["embedding"]))
        return result

    # ── Cost / audit ───────────────────────────────────────────────────────────

    def log_cost(self, provider: str, cost_usd: float) -> None:
        from google.cloud import firestore  # type: ignore[import]

        today = date.today().isoformat()
        ref = self._db().collection("cost_log").document(f"{today}_{provider}")
        ref.set(
            {
                "date": today,
                "provider": provider,
                "calls": firestore.Increment(1),
                "cost_usd": firestore.Increment(cost_usd),
            },
            merge=True,
        )

    def get_daily_spend(self) -> float:
        today = date.today().isoformat()
        docs = self._db().collection("cost_log").where("date", "==", today).stream()
        return sum(doc.to_dict().get("cost_usd", 0.0) for doc in docs)

    def log_audit(
        self,
        ip_hash: str,
        query_hash: str,
        input_type: str,
        provider: str,
        tier_used: int,
        cost_usd: float,
        status: str,
    ) -> None:
        from google.cloud import firestore  # type: ignore[import]

        self._db().collection("audit_log").add({
            "ip_hash": ip_hash,
            "query_hash": query_hash,
            "input_type": input_type,
            "provider": provider,
            "tier_used": tier_used,
            "cost_usd": cost_usd,
            "status": status,
            "created_at": firestore.SERVER_TIMESTAMP,
        })
