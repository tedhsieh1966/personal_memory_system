"""Tests for LTM service: upsert, list, delete, vector search, merge-on-similarity."""
from __future__ import annotations

import pytest

from pms.api.services import ltm

DIM = 4  # matches conftest dim=4


def _vec(*vals):
    """Build a DIM-length float list. Pads with 0.0 or truncates."""
    v = list(vals) + [0.0] * DIM
    return [float(x) for x in v[:DIM]]


class TestCountAndInit:
    def test_count_starts_at_zero(self):
        assert ltm.count() == 0

    def test_list_empty(self):
        assert ltm.list_concepts() == []


class TestUpsert:
    def test_insert_returns_uuid(self):
        cid = ltm.upsert_concept("User prefers Python", _vec(1, 0, 0, 0), ["ep1"])
        assert isinstance(cid, str) and len(cid) == 36

    def test_count_increments(self):
        ltm.upsert_concept("Concept A", _vec(1, 0, 0, 0), ["ep1"])
        assert ltm.count() == 1

    def test_list_returns_concept(self):
        ltm.upsert_concept("Durable fact about the user", _vec(1, 0, 0, 0), ["ep1"])
        rows = ltm.list_concepts()
        assert any("Durable fact" in r["concept"] for r in rows)

    def test_no_vector_in_list_results(self):
        ltm.upsert_concept("Concept", _vec(1, 0, 0, 0), ["ep1"])
        rows = ltm.list_concepts()
        for r in rows:
            assert "vector" not in r

    def test_similar_concept_merges(self):
        """Two identical-direction vectors → cosine sim = 1.0 → should merge."""
        id1 = ltm.upsert_concept("User uses Python", _vec(1, 1, 0, 0), ["ep1"])
        id2 = ltm.upsert_concept("User writes Python code", _vec(2, 2, 0, 0), ["ep2"])
        assert id1 == id2                 # merged, same id
        assert ltm.count() == 1

    def test_different_concept_inserts_new(self):
        """Orthogonal vectors → cosine sim = 0 → separate entries."""
        ltm.upsert_concept("Concept X", _vec(1, 0, 0, 0), ["ep1"])
        ltm.upsert_concept("Concept Y", _vec(0, 1, 0, 0), ["ep2"])
        assert ltm.count() == 2

    def test_merged_concept_accumulates_ep_ids(self):
        ltm.upsert_concept("Same direction A", _vec(1, 0, 0, 0), ["ep1"])
        ltm.upsert_concept("Same direction B", _vec(5, 0, 0, 0), ["ep2"])
        rows = ltm.list_concepts()
        ep_ids = rows[0]["source_ep_ids"]
        assert "ep1" in ep_ids and "ep2" in ep_ids


class TestDelete:
    def test_delete_removes_concept(self):
        cid = ltm.upsert_concept("To delete", _vec(1, 0, 0, 0), ["ep1"])
        assert ltm.delete_concept(cid) is True
        assert ltm.count() == 0

    def test_delete_nonexistent_returns_false(self):
        assert ltm.delete_concept("00000000-0000-0000-0000-000000000000") is False


class TestVectorSearch:
    def test_finds_closest_concept(self):
        ltm.upsert_concept("Python programming language", _vec(1, 0, 0, 0), ["ep1"])
        ltm.upsert_concept("Database storage systems", _vec(0, 1, 0, 0), ["ep2"])
        # Query close to first concept
        hits = ltm.vector_search(_vec(1, 0.01, 0, 0), top_k=1)
        assert len(hits) == 1
        assert "Python" in hits[0]["concept"]

    def test_distance_present_in_results(self):
        ltm.upsert_concept("Concept", _vec(1, 0, 0, 0), ["ep1"])
        hits = ltm.vector_search(_vec(1, 0, 0, 0), top_k=1)
        assert "_distance" in hits[0]
        assert 0.0 <= hits[0]["_distance"] <= 1.0 + 1e-6

    def test_exact_match_distance_near_zero(self):
        ltm.upsert_concept("Exact match test", _vec(1, 0, 0, 0), ["ep1"])
        hits = ltm.vector_search(_vec(1, 0, 0, 0), top_k=1)
        assert hits[0]["_distance"] == pytest.approx(0.0, abs=1e-4)

    def test_empty_table_returns_empty(self):
        hits = ltm.vector_search(_vec(1, 0, 0, 0), top_k=5)
        assert hits == []
