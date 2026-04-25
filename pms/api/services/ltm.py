from __future__ import annotations

import time
import uuid
from typing import Any

try:
    import lancedb
    import pyarrow as pa
    _LANCEDB_AVAILABLE = True
except ImportError:
    _LANCEDB_AVAILABLE = False

from ..config import get_config

_db = None
_table = None


def _get_table():
    global _db, _table
    if not _LANCEDB_AVAILABLE:
        raise ImportError("lancedb and pyarrow are required for LTM (Phase 2)")
    if _table is None:
        cfg = get_config()
        ltm_path: str = cfg["storage"]["ltm_path"]
        dim: int = cfg["embedding"]["dim"]
        _db = lancedb.connect(ltm_path)
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("concept", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
            pa.field("source_ep_ids", pa.list_(pa.string())),
            pa.field("created_at", pa.float64()),
            pa.field("updated_at", pa.float64()),
        ])
        if "ltm_concepts" not in _db.list_tables():
            _table = _db.create_table("ltm_concepts", schema=schema)
        else:
            _table = _db.open_table("ltm_concepts")
    return _table


def init() -> None:
    """Eagerly initialise LanceDB on startup (optional)."""
    if _LANCEDB_AVAILABLE:
        try:
            _get_table()
        except Exception:
            pass


def count() -> int:
    if not _LANCEDB_AVAILABLE:
        return 0
    try:
        return _get_table().count_rows()
    except Exception:
        return 0


def list_concepts(limit: int = 50, offset: int = 0) -> list[dict]:
    if not _LANCEDB_AVAILABLE:
        return []
    try:
        rows = (
            _get_table()
            .search()
            .limit(limit + offset)
            .to_list()
        )
        # Manual offset since LanceDB scan doesn't expose SQL OFFSET cleanly
        return [_clean(r) for r in rows[offset:offset + limit]]
    except Exception:
        return []


def delete_concept(concept_id: str) -> bool:
    try:
        table = _get_table()
        before = table.count_rows()
        table.delete(f"id = '{concept_id}'")
        return table.count_rows() < before
    except Exception as exc:
        raise RuntimeError(f"LTM delete failed: {exc}") from exc


def upsert_concept(
    concept: str,
    vector: list[float],
    source_ep_ids: list[str],
) -> str:
    """Insert a new concept or merge into an existing one if cosine similarity > threshold."""
    cfg = get_config()
    merge_threshold: float = cfg["memory"]["ltm_merge_cosine"]
    table = _get_table()
    now = time.time()

    # Check for a near-duplicate
    hits = (
        table.search(vector, vector_column_name="vector")
        .metric("cosine")
        .limit(1)
        .to_list()
    )
    if hits and (1.0 - hits[0]["_distance"]) >= merge_threshold:
        existing = hits[0]
        existing_id: str = existing["id"]
        merged_ep_ids = list(dict.fromkeys((existing.get("source_ep_ids") or []) + source_ep_ids))
        table.delete(f"id = '{existing_id}'")
        table.add([{
            "id": existing_id,
            "concept": existing["concept"],
            "vector": vector,
            "source_ep_ids": merged_ep_ids,
            "created_at": float(existing["created_at"]),
            "updated_at": now,
        }])
        return existing_id

    new_id = str(uuid.uuid4())
    table.add([{
        "id": new_id,
        "concept": concept,
        "vector": vector,
        "source_ep_ids": source_ep_ids,
        "created_at": now,
        "updated_at": now,
    }])
    return new_id


def vector_search(query_vector: list[float], top_k: int = 10) -> list[dict]:
    if not _LANCEDB_AVAILABLE:
        return []
    try:
        rows = (
            _get_table()
            .search(query_vector, vector_column_name="vector")
            .metric("cosine")
            .limit(top_k)
            .to_list()
        )
        return [_clean(r) for r in rows]
    except Exception:
        return []


def _clean(row: dict) -> dict:
    d = dict(row)
    d.pop("vector", None)  # don't return raw vectors to callers
    return d
