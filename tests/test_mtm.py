"""Tests for MTM service: insert, list, delete, patch, decay, BM25 search."""
from __future__ import annotations

import math
import time

import pytest

from pms.service import mtm


def _episode(summary="User worked on Python project", score=5.0, tags=None, access=0):
    eid = mtm.insert(summary, tags or ["python", "dev"], score, [1, 2])
    if access:
        from pms.service.db import get_conn
        conn = get_conn()
        with conn:
            conn.execute(
                "UPDATE mtm_episodes SET access_count=? WHERE id=?", (access, eid)
            )
    return eid


class TestInsertAndList:
    def test_insert_returns_id(self):
        eid = _episode()
        assert isinstance(eid, int)

    def test_list_returns_episode(self):
        eid = _episode("Unique summary alpha beta")
        rows = mtm.list_episodes(limit=20)
        assert any(r["id"] == eid for r in rows)

    def test_list_min_score_filter(self):
        low = _episode("low importance", score=2.0)
        high = _episode("high importance", score=8.0)
        rows = mtm.list_episodes(min_score=5.0)
        ids = [r["id"] for r in rows]
        assert high in ids
        assert low not in ids

    def test_topic_tags_round_trip(self):
        eid = _episode(tags=["fastapi", "sqlite", "memory"])
        row = mtm.get_episode(eid)
        assert set(row["topic_tags"]) == {"fastapi", "sqlite", "memory"}

    def test_pinned_defaults_false(self):
        eid = _episode()
        row = mtm.get_episode(eid)
        assert row["pinned"] is False


class TestDelete:
    def test_delete_removes_episode(self):
        eid = _episode()
        assert mtm.delete_episode(eid) is True
        assert mtm.get_episode(eid) is None

    def test_delete_nonexistent_returns_false(self):
        assert mtm.delete_episode(99999) is False


class TestPatch:
    def test_patch_pin(self):
        eid = _episode()
        assert mtm.patch_episode(eid, pinned=True, importance_score=None) is True
        assert mtm.get_episode(eid)["pinned"] is True

    def test_patch_score(self):
        eid = _episode(score=5.0)
        mtm.patch_episode(eid, pinned=None, importance_score=9.5)
        assert mtm.get_episode(eid)["importance_score"] == pytest.approx(9.5)

    def test_patch_nonexistent_returns_false(self):
        assert mtm.patch_episode(99999, pinned=True, importance_score=None) is False

    def test_patch_no_fields_returns_false(self):
        eid = _episode()
        assert mtm.patch_episode(eid, pinned=None, importance_score=None) is False


class TestDecay:
    def test_decay_reduces_score(self):
        eid = _episode(score=8.0)
        # Set last_accessed to 30 days ago
        from pms.service.db import get_conn
        conn = get_conn()
        past = time.time() - 30 * 86400
        with conn:
            conn.execute("UPDATE mtm_episodes SET last_accessed=? WHERE id=?", (past, eid))
        mtm.apply_decay()
        row = mtm.get_episode(eid)
        # score = 8 * exp(-0.05 * 30) ≈ 8 * exp(-1.5) ≈ 1.78
        expected = 8.0 * math.exp(-0.05 * 30)
        assert row is not None
        assert row["importance_score"] == pytest.approx(expected, rel=0.01)

    def test_decay_deletes_below_threshold(self):
        eid = _episode(score=0.9)  # below threshold of 1.0 after any decay
        from pms.service.db import get_conn
        conn = get_conn()
        past = time.time() - 1 * 86400
        with conn:
            conn.execute("UPDATE mtm_episodes SET last_accessed=? WHERE id=?", (past, eid))
        mtm.apply_decay()
        # 0.9 * exp(-0.05 * 1) ≈ 0.856 < 1.0 → should be deleted
        assert mtm.get_episode(eid) is None

    def test_pinned_episodes_survive_decay(self):
        eid = _episode(score=0.5)
        mtm.patch_episode(eid, pinned=True, importance_score=None)
        from pms.service.db import get_conn
        conn = get_conn()
        past = time.time() - 100 * 86400
        with conn:
            conn.execute("UPDATE mtm_episodes SET last_accessed=? WHERE id=?", (past, eid))
        mtm.apply_decay()
        assert mtm.get_episode(eid) is not None  # pinned, survives

    def test_bump_access_resets_score_to_10(self):
        eid = _episode(score=3.0)
        mtm.bump_access(eid)
        assert mtm.get_episode(eid)["importance_score"] == pytest.approx(10.0)
        assert mtm.get_episode(eid)["access_count"] == 1


class TestBM25Search:
    def test_finds_matching_episode(self):
        _episode("User studied Ebbinghaus memory decay exponential formula")
        hits = mtm.bm25_search("Ebbinghaus decay", top_k=5)
        assert any("Ebbinghaus" in h["summary"] for h in hits)

    def test_rank_present(self):
        _episode("Python vector database LanceDB embeddings")
        hits = mtm.bm25_search("vector database", top_k=5)
        for h in hits:
            assert "rank" in h
            assert h["rank"] <= 0
