from __future__ import annotations

import json
import math
import re
import time
from typing import Any

from ..db import get_conn


def _now() -> float:
    return time.time()


def insert(
    summary: str,
    topic_tags: list[str],
    importance_score: float,
    source_ids: list[int],
) -> int:
    from ..config import get_config
    cfg = get_config()
    ttl_days: int = cfg["memory"]["mtm_ttl_days"]

    created_at = _now()
    expires_at = created_at + ttl_days * 86400

    conn = get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO mtm_episodes "
            "(summary, topic_tags, importance_score, source_ids, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                summary,
                json.dumps(topic_tags),
                importance_score,
                json.dumps(source_ids),
                created_at,
                expires_at,
            ),
        )
    return cur.lastrowid  # type: ignore[return-value]


def list_episodes(
    limit: int = 50,
    offset: int = 0,
    min_score: float | None = None,
) -> list[dict]:
    conn = get_conn()
    if min_score is not None:
        rows = conn.execute(
            "SELECT * FROM mtm_episodes WHERE importance_score >= ? "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (min_score, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM mtm_episodes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_episode(ep_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM mtm_episodes WHERE id = ?", (ep_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_episode(ep_id: int) -> bool:
    conn = get_conn()
    with conn:
        cur = conn.execute("DELETE FROM mtm_episodes WHERE id = ?", (ep_id,))
    return cur.rowcount > 0


def patch_episode(
    ep_id: int,
    pinned: bool | None,
    importance_score: float | None,
) -> bool:
    updates: dict[str, Any] = {}
    if pinned is not None:
        updates["pinned"] = int(pinned)
    if importance_score is not None:
        updates["importance_score"] = importance_score
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [ep_id]

    conn = get_conn()
    with conn:
        cur = conn.execute(
            f"UPDATE mtm_episodes SET {set_clause} WHERE id = ?", values
        )
    return cur.rowcount > 0


def bump_access(ep_id: int) -> None:
    conn = get_conn()
    now = _now()
    with conn:
        conn.execute(
            "UPDATE mtm_episodes "
            "SET access_count = access_count + 1, last_accessed = ?, importance_score = 10.0 "
            "WHERE id = ?",
            (now, ep_id),
        )


def count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM mtm_episodes").fetchone()[0]


def apply_decay() -> int:
    """Apply Ebbinghaus decay to all non-pinned episodes; delete those below threshold."""
    from ..config import get_config
    cfg = get_config()
    lam: float = cfg["memory"]["mtm_decay_lambda"]
    threshold: float = cfg["memory"]["mtm_score_threshold"]

    conn = get_conn()
    now = _now()
    rows = conn.execute(
        "SELECT id, importance_score, last_accessed FROM mtm_episodes WHERE pinned = 0"
    ).fetchall()

    updated = 0
    to_delete: list[int] = []
    with conn:
        for row in rows:
            ep_id, score, last_accessed = row[0], row[1], row[2]
            ref_ts = last_accessed if last_accessed else now
            days = (now - ref_ts) / 86400
            new_score = score * math.exp(-lam * days)
            if new_score < threshold:
                to_delete.append(ep_id)
            else:
                conn.execute(
                    "UPDATE mtm_episodes SET importance_score = ? WHERE id = ?",
                    (new_score, ep_id),
                )
                updated += 1

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(
                f"DELETE FROM mtm_episodes WHERE id IN ({placeholders})", to_delete
            )

    return updated


def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    fts_query = _build_fts_query(query)
    if not fts_query:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT m.*, mtm_fts.rank
            FROM mtm_fts
            JOIN mtm_episodes m ON m.id = mtm_fts.rowid
            WHERE mtm_fts MATCH ?
            ORDER BY mtm_fts.rank
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
    for field in ("topic_tags", "source_ids"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    d["pinned"] = bool(d.get("pinned", 0))
    if not include_rank:
        d.pop("rank", None)
    return d
