import os
import time
import json
import sqlite3
from typing import Optional

DB_PATH = os.getenv("MEMORY_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "memory.db"))

TTL_BY_CATEGORY = {
    "pricing": 6 * 3600,
    "version": 12 * 3600,
    "leadership": 24 * 3600,
    "law": 72 * 3600,
    "other": 24 * 3600,
}

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    return conn

def put(key: str, value: list[dict], category: str = "other") -> None:
    ttl = TTL_BY_CATEGORY.get(category.lower(), TTL_BY_CATEGORY["other"])
    expires_at = time.time() + ttl
    val_json = json.dumps(value)
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO evidence_cache (key, value, category, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                expires_at = excluded.expires_at
            """,
            (key, val_json, category.lower(), expires_at)
        )

def set(key: str, value: list[dict], category: str = "other") -> None:
    put(key, value, category)

def get(key: str) -> Optional[list[dict]]:
    now = time.time()
    with _get_connection() as conn:
        cur = conn.execute(
            "SELECT value, expires_at FROM evidence_cache WHERE key = ?",
            (key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        val_json, expires_at = row
        if now > expires_at:
            conn.execute("DELETE FROM evidence_cache WHERE key = ?", (key,))
            return None
        try:
            return json.loads(val_json)
        except Exception:
            return None

def stats() -> dict:
    now = time.time()
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM evidence_cache").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM evidence_cache WHERE expires_at > ?", (now,)).fetchone()[0]
        expired = total - active
    return {
        "total_entries": total,
        "active_entries": active,
        "expired_entries": expired
    }

def clear() -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM evidence_cache")

# Alias for backward compatibility
set = put

