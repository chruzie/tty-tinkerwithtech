"""SQLite cache repository for tty-theme (repository pattern)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

_DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "tty-theme" / "cache.db"


class ThemeRepository:
    """Repository for theme cache, cost log, and audit log."""

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001, S110
            pass

    def init_db(self) -> None:
        """Create all tables and indexes (idempotent)."""
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS themes (
                    id          INTEGER PRIMARY KEY,
                    query_hash  TEXT NOT NULL UNIQUE,
                    query_raw   TEXT,
                    input_type  TEXT NOT NULL,
                    name        TEXT,
                    theme_data  TEXT NOT NULL,
                    embedding   TEXT,
                    source      TEXT DEFAULT 'ai',
                    provider    TEXT,
                    cost_usd    REAL DEFAULT 0.0,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_themes_query_hash
                    ON themes(query_hash);

                CREATE TABLE IF NOT EXISTS cost_log (
                    id        INTEGER PRIMARY KEY,
                    date      TEXT NOT NULL,
                    provider  TEXT NOT NULL,
                    calls     INTEGER DEFAULT 0,
                    cost_usd  REAL DEFAULT 0.0,
                    UNIQUE(date, provider)
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY,
                    ip_hash     TEXT,
                    query_hash  TEXT,
                    input_type  TEXT,
                    provider    TEXT,
                    tier_used   INTEGER,
                    cost_usd    REAL,
                    status      TEXT,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    ip_hash     TEXT PRIMARY KEY,
                    tokens      REAL NOT NULL DEFAULT 10.0,
                    last_refill TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

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
    ) -> int:
        """Insert a theme row; returns new row id."""
        embedding_json = json.dumps(embedding) if embedding is not None else None
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO themes
                    (query_hash, query_raw, input_type, name, theme_data,
                     embedding, source, provider, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (query_hash, query_raw, input_type, name, theme_data,
                 embedding_json, source, provider, cost_usd),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_by_hash(self, query_hash: str) -> dict[str, Any] | None:
        """Return the most recent theme matching query_hash, or None."""
        row = self._conn.execute(
            "SELECT * FROM themes WHERE query_hash = ? ORDER BY id DESC LIMIT 1",
            (query_hash,),
        ).fetchone()
        return dict(row) if row else None

    def get_by_id(self, theme_id: int) -> dict[str, Any] | None:
        """Return a theme row by primary key."""
        row = self._conn.execute(
            "SELECT * FROM themes WHERE id = ?", (theme_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_themes(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent themes (most recent first)."""
        rows = self._conn.execute(
            "SELECT * FROM themes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_embeddings(self) -> list[tuple[int, list[float]]]:
        """Return (id, vector) for all themes that have an embedding."""
        rows = self._conn.execute(
            "SELECT id, embedding FROM themes WHERE embedding IS NOT NULL"
        ).fetchall()
        result = []
        for row in rows:
            vector: list[float] = json.loads(row["embedding"])
            result.append((row["id"], vector))
        return result

    def log_cost(self, provider: str, cost_usd: float) -> None:
        """Upsert into cost_log for today (atomic, no TOCTOU race)."""
        today = date.today().isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO cost_log (date, provider, calls, cost_usd)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(date, provider)
                DO UPDATE SET calls = calls + 1, cost_usd = cost_usd + excluded.cost_usd
                """,
                (today, provider, cost_usd),
            )

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
        """Append an audit log row."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_log
                    (ip_hash, query_hash, input_type, provider, tier_used, cost_usd, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ip_hash, query_hash, input_type, provider, tier_used, cost_usd, status),
            )

    def get_daily_spend(self) -> float:
        """Return total cost_usd spent today across all providers."""
        today = date.today().isoformat()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM cost_log WHERE date = ?",
            (today,),
        ).fetchone()
        return float(row["total"])
