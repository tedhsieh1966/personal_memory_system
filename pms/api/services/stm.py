from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from ..config import get_config
from ..db import get_conn


def _now() -> float:
    return time.time()


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r'\b[a-zA-Z]\w{2,}\b', text.lower())
    return list(dict.fromkeys(words))[:30]


def insert(
    source: str,
    content: str,
    timestamp: datetime | None,
    metadata: dict[str, Any] | None,
) -> int:
    cfg = get_config()
    ttl_hours: int = cfg["memory"]["stm_ttl_hours"]
    capacity: int = cfg["memory"]["stm_capacity"]

    created_at = timestamp.timestamp() if timestamp else _now()
    expires_at = created_at + ttl_hours * 3600
    keywords = _extract_keywords(content)

    conn = get_conn()
    with conn:
        current_count: int = conn.execute("SELECT COUNT(*) FROM stm_events").fetchone()[0]
        if current_count >= capacity:
            oldest = conn.execute(
                "SELECT id FROM stm_events ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if oldest:
                conn.execute("DELETE FROM stm_events WHERE id = ?", (oldest[0],))

        cur = conn.execute(
            "INSERT INTO stm_events (source, content, keywords, metadata, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                source,
                content,
                json.dumps(keywords),
                json.dumps(metadata) if metadata else None,
                created_at,
                expires_at,
            ),
        )
    return cur.lastrowid  # type: ignore[return-value]


def list_events(limit: int = 50, offset: int = 0) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM stm_events ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_event(event_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM stm_events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_event(event_id: int) -> bool:
    conn = get_conn()
    with conn:
        cur = conn.execute("DELETE FROM stm_events WHERE id = ?", (event_id,))
    return cur.rowcount > 0


def count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM stm_events").fetchone()[0]


def delete_expired() -> int:
    """Delete all STM events past their TTL. Called by the maintenance cycle."""
    conn = get_conn()
    with conn:
        cur = conn.execute("DELETE FROM stm_events WHERE expires_at < ?", (_now(),))
    return cur.rowcount


def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    fts_query = _build_fts_query(query)
    if not fts_query:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.*, stm_fts.rank
            FROM stm_fts
            JOIN stm_events s ON s.id = stm_fts.rowid
            WHERE stm_fts MATCH ?
            ORDER BY stm_fts.rank
            LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()
    except Exception:
        return []
    return [_row_to_dict(r, include_rank=True) for r in rows]


def _build_fts_query(q: str) -> str | None:
    clean = re.sub(r'[^\w\s]', ' ', q)
    tokens = [t for t in clean.split() if len(t) >= 2]
    if not tokens:
        return None
    return ' OR '.join(tokens)


def _row_to_dict(row: Any, include_rank: bool = False) -> dict:
    d = dict(row)
    if d.get("keywords"):
        try:
            d["keywords"] = json.loads(d["keywords"])
        except (json.JSONDecodeError, TypeError):
            d["keywords"] = []
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
    if not include_rank:
        d.pop("rank", None)
    return d
