"""Integration tests for the FastAPI endpoints via TestClient."""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a fresh TestClient for each test, bypassing the scheduler."""
    from pms.server.main import app
    with patch("pms.service.scheduler.start"), patch("pms.service.scheduler.stop"):
        with TestClient(app) as c:
            yield c


class TestIngest:
    def test_ingest_manual(self, client):
        resp = client.post("/ingest", json={"source": "manual", "content": "test note"})
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["tier"] == "stm"

    def test_ingest_ai_chat(self, client):
        resp = client.post(
            "/ingest",
            json={"source": "ai_chat", "content": "Discussed neural networks", "metadata": {"model": "gpt4"}},
        )
        assert resp.status_code == 201

    def test_ingest_invalid_source_rejected(self, client):
        resp = client.post("/ingest", json={"source": "unknown", "content": "bad"})
        assert resp.status_code == 422

    def test_ingest_missing_content_rejected(self, client):
        resp = client.post("/ingest", json={"source": "manual"})
        assert resp.status_code == 422


class TestRetrieve:
    def test_retrieve_returns_results(self, client):
        client.post("/ingest", json={"source": "manual", "content": "Python FastAPI server code"})
        resp = client.get("/retrieve?q=Python+FastAPI")
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "partial" in body

    def test_retrieve_requires_q(self, client):
        resp = client.get("/retrieve")
        assert resp.status_code == 422

    def test_retrieve_top_k_respected(self, client):
        for i in range(5):
            client.post("/ingest", json={"source": "manual", "content": f"content keyword item {i}"})
        resp = client.get("/retrieve?q=content+keyword&top_k=2")
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 2

    def test_retrieve_no_results_on_mismatch(self, client):
        client.post("/ingest", json={"source": "manual", "content": "completely different topic here"})
        resp = client.get("/retrieve?q=xyzzy+frobozz+impossible")
        assert resp.status_code == 200
        assert resp.json()["results"] == []


class TestMemoryCRUD:
    def test_list_stm(self, client):
        client.post("/ingest", json={"source": "manual", "content": "hello"})
        resp = client.get("/memory/stm")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_stm(self, client):
        r = client.post("/ingest", json={"source": "manual", "content": "to delete"})
        eid = r.json()["id"]
        resp = client.delete(f"/memory/stm/{eid}")
        assert resp.status_code == 204
        # Should be gone
        stm_list = client.get("/memory/stm").json()
        assert not any(e["id"] == eid for e in stm_list)

    def test_delete_stm_404(self, client):
        resp = client.delete("/memory/stm/99999")
        assert resp.status_code == 404

    def test_list_mtm_empty(self, client):
        resp = client.get("/memory/mtm")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_ltm_empty(self, client):
        resp = client.get("/memory/ltm")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAdmin:
    def test_status(self, client):
        client.post("/ingest", json={"source": "manual", "content": "status test"})
        resp = client.get("/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stm_count"] >= 1
        assert body["mtm_count"] == 0
        assert body["ltm_count"] == 0
        assert "scheduler_running" in body

    def test_config_get_redacts_api_key(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        cfg = resp.json()
        assert cfg["ai_backend"]["local"]["api_key"] == "***"
        assert cfg["ai_backend"]["cloud"]["api_key"] == "***"

    def test_config_post_updates_value(self, client):
        resp = client.post("/config", json={"config": {"memory": {"stm_ttl_hours": 24}}})
        assert resp.status_code == 200
        updated = client.get("/config").json()
        assert updated["memory"]["stm_ttl_hours"] == 24

    def test_consolidate_stm_no_events(self, client):
        resp = client.post("/consolidate/stm")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("batches_processed") == 0

    def test_consolidate_stm_with_old_events(self, client):
        client.post("/ingest", json={"source": "manual", "content": "old event to consolidate"})
        # Backdate the event
        from pms.service.db import get_conn
        conn = get_conn()
        past = time.time() - 8 * 3600
        with conn:
            conn.execute("UPDATE stm_events SET created_at=? WHERE 1=1", (past,))

        ai_payload = json.dumps({
            "summary": "User worked on memory consolidation system.",
            "topic_tags": ["memory", "python"],
            "importance_score": 7,
        })
        with patch("pms.service.consolidator._chat", return_value=ai_payload):
            resp = client.post("/consolidate/stm")

        assert resp.status_code == 200
        body = resp.json()
        assert body["batches_processed"] == 1
        assert body["events_consolidated"] == 1
