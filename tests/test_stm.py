"""Tests for STM service: insert, list, delete, BM25 search, TTL, ring-buffer eviction."""
from __future__ import annotations

import time

import pytest

from pms.service import stm


def _insert(content="hello world testing", source="manual"):
    return stm.insert(source, content, None, None)


class TestInsertAndList:
    def test_insert_returns_id(self):
        eid = _insert()
        assert isinstance(eid, int)
        assert eid >= 1

    def test_list_returns_inserted_event(self):
        eid = _insert("unique content xyz")
        rows = stm.list_events(limit=10)
        ids = [r["id"] for r in rows]
        assert eid in ids

    def test_list_respects_limit(self):
        for _ in range(5):
            _insert()
        rows = stm.list_events(limit=3)
        assert len(rows) <= 3

    def test_list_respects_offset(self):
        for i in range(4):
            _insert(f"event {i}")
        page1 = stm.list_events(limit=2, offset=0)
        page2 = stm.list_events(limit=2, offset=2)
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        assert ids1.isdisjoint(ids2)

    def test_keywords_extracted(self):
        _insert("Python FastAPI server application")
        rows = stm.list_events(limit=1)
        kws = rows[0]["keywords"]
        assert isinstance(kws, list)
        assert any("python" in k or "fastapi" in k for k in kws)

    def test_metadata_round_trips(self):
        eid = stm.insert("manual", "test", None, {"url": "http://example.com", "tab": 3})
        ev = stm.get_event(eid)
        assert ev["metadata"]["url"] == "http://example.com"
        assert ev["metadata"]["tab"] == 3


class TestDelete:
    def test_delete_removes_event(self):
        eid = _insert()
        assert stm.delete_event(eid) is True
        assert stm.get_event(eid) is None

    def test_delete_nonexistent_returns_false(self):
        assert stm.delete_event(99999) is False

    def test_count_decrements_after_delete(self):
        eid = _insert()
        before = stm.count()
        stm.delete_event(eid)
        assert stm.count() == before - 1


class TestRingBuffer:
    def test_evicts_oldest_when_at_capacity(self):
        """Capacity is set to 10 in conftest; inserting 11 should evict the oldest."""
        ids = [_insert(f"event {i}") for i in range(10)]
        assert stm.count() == 10
        new_id = _insert("overflow event")
        assert stm.count() == 10   # still 10
        assert stm.get_event(ids[0]) is None  # oldest evicted
        assert stm.get_event(new_id) is not None


class TestTTL:
    def test_delete_expired_removes_old_events(self, monkeypatch):
        eid = _insert("expiring event")
        # Manually set expires_at to the past
        from pms.service.db import get_conn
        conn = get_conn()
        with conn:
            conn.execute("UPDATE stm_events SET expires_at = ? WHERE id = ?", (time.time() - 1, eid))
        removed = stm.delete_expired()
        assert removed >= 1
        assert stm.get_event(eid) is None

    def test_non_expired_events_survive(self):
        eid = _insert()
        stm.delete_expired()
        assert stm.get_event(eid) is not None


class TestBM25Search:
    def test_finds_matching_event(self):
        stm.insert("manual", "Python FastAPI REST API development", None, None)
        hits = stm.bm25_search("FastAPI REST", top_k=5)
        assert any("FastAPI" in h["content"] or "fastapi" in h["content"].lower() for h in hits)

    def test_returns_empty_for_no_match(self):
        stm.insert("manual", "completely unrelated content here", None, None)
        hits = stm.bm25_search("xyzzy frobozz nonexistent", top_k=5)
        assert hits == []

    def test_rank_present_when_include_rank(self):
        stm.insert("manual", "searchable keyword content", None, None)
        hits = stm.bm25_search("searchable keyword", top_k=5)
        for h in hits:
            assert "rank" in h
            assert h["rank"] <= 0  # FTS5 BM25 ranks are non-positive

    def test_empty_query_returns_empty(self):
        _insert()
        hits = stm.bm25_search("", top_k=5)
        assert hits == []
