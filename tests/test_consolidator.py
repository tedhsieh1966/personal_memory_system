"""Tests for consolidator: maintenance, STM→MTM with mocked AI, MTM→LTM with mocked AI+embedder."""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from pms.api.services import consolidator, mtm, stm


def _stm_event(content="sample content", age_hours=7, source="manual"):
    """Insert an STM event backdated by age_hours."""
    eid = stm.insert(source, content, None, None)
    past = time.time() - age_hours * 3600
    from pms.api.db import get_conn
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE stm_events SET created_at=?, expires_at=? WHERE id=?",
            (past, past + 12 * 3600, eid),
        )
    return eid


def _mtm_episode(summary="Test episode", score=8.0, access=2):
    eid = mtm.insert(summary, ["test"], score, [1])
    from pms.api.db import get_conn
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE mtm_episodes SET access_count=? WHERE id=?", (access, eid)
        )
    return eid


class TestMaintenance:
    def test_deletes_expired_stm(self):
        eid = stm.insert("manual", "will expire", None, None)
        from pms.api.db import get_conn
        conn = get_conn()
        with conn:
            conn.execute("UPDATE stm_events SET expires_at=? WHERE id=?", (time.time() - 1, eid))
        result = consolidator.run_maintenance()
        assert result["stm_deleted"] >= 1
        assert stm.get_event(eid) is None

    def test_applies_mtm_decay(self):
        eid = _mtm_episode(score=5.0)
        from pms.api.db import get_conn
        conn = get_conn()
        with conn:
            conn.execute(
                "UPDATE mtm_episodes SET last_accessed=? WHERE id=?",
                (time.time() - 10 * 86400, eid),
            )
        consolidator.run_maintenance()
        ep = mtm.get_episode(eid)
        assert ep is not None
        assert ep["importance_score"] < 5.0

    def test_returns_count_dict(self):
        result = consolidator.run_maintenance()
        assert "stm_deleted" in result
        assert "mtm_updated" in result


class TestSTMtoMTM:
    def _mock_ai_response(self, summary="Summary text.", tags=None, score=7):
        payload = json.dumps({
            "summary": summary,
            "topic_tags": tags or ["python", "dev"],
            "importance_score": score,
        })
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = payload
        return mock_resp

    def test_no_events_returns_zeros(self):
        result = consolidator.run_stm_to_mtm()
        assert result == {"batches_processed": 0, "events_consolidated": 0}

    def test_recent_events_not_consolidated(self):
        """Events younger than stm_trigger_hours should not be touched."""
        stm.insert("manual", "brand new event", None, None)
        result = consolidator.run_stm_to_mtm()
        assert result["events_consolidated"] == 0

    def test_old_events_consolidated(self):
        _stm_event("old event alpha", age_hours=7)
        _stm_event("old event beta", age_hours=8)
        mock_resp = self._mock_ai_response("Two old events processed.")

        with patch.object(consolidator, "_chat", return_value=mock_resp.choices[0].message.content):
            result = consolidator.run_stm_to_mtm()

        assert result["batches_processed"] == 1
        assert result["events_consolidated"] == 2
        assert mtm.count() == 1
        assert stm.count() == 0  # all consolidated events deleted

    def test_ai_failure_skips_batch(self):
        _stm_event("old event", age_hours=7)
        with patch.object(consolidator, "_chat", return_value=None):
            result = consolidator.run_stm_to_mtm()
        assert result["batches_processed"] == 0
        assert stm.count() == 1  # event not deleted

    def test_bad_json_skips_batch(self):
        _stm_event("old event", age_hours=7)
        with patch.object(consolidator, "_chat", return_value="not valid json {{"):
            result = consolidator.run_stm_to_mtm()
        assert result["batches_processed"] == 0

    def test_score_clamped_to_1_10(self):
        _stm_event("old event", age_hours=7)
        payload = json.dumps({"summary": "x", "topic_tags": [], "importance_score": 999})
        with patch.object(consolidator, "_chat", return_value=payload):
            consolidator.run_stm_to_mtm()
        eps = mtm.list_episodes()
        assert eps[0]["importance_score"] == pytest.approx(10.0)


class TestMTMtoLTM:
    def test_no_eligible_episodes_returns_zeros(self):
        """Episodes with score < 7 or access < 2 are skipped."""
        _mtm_episode(score=5.0, access=0)
        result = consolidator.run_mtm_to_ltm()
        assert result == {"episodes_processed": 0, "concepts_created": 0}

    def test_eligible_episodes_distilled(self):
        _mtm_episode("User regularly writes Python", score=8.0, access=2)
        concepts_payload = json.dumps(["User is proficient in Python."])

        with (
            patch.object(consolidator, "_chat", return_value=concepts_payload),
            patch("pms.api.services.consolidator.embedder.embed", return_value=[1.0, 0.0, 0.0, 0.0]),
        ):
            result = consolidator.run_mtm_to_ltm()

        assert result["episodes_processed"] == 1
        assert result["concepts_created"] == 1
        from pms.api.services import ltm
        assert ltm.count() == 1

    def test_ai_failure_returns_zeros(self):
        _mtm_episode(score=8.0, access=2)
        with patch.object(consolidator, "_chat", return_value=None):
            result = consolidator.run_mtm_to_ltm()
        assert result["concepts_created"] == 0

    def test_embedding_failure_skips_concept(self):
        _mtm_episode(score=8.0, access=2)
        concepts_payload = json.dumps(["Some concept here."])
        with (
            patch.object(consolidator, "_chat", return_value=concepts_payload),
            patch("pms.api.services.consolidator.embedder.embed", return_value=None),
        ):
            result = consolidator.run_mtm_to_ltm()
        assert result["concepts_created"] == 0

    def test_non_string_concepts_skipped(self):
        _mtm_episode(score=8.0, access=2)
        payload = json.dumps(["Valid concept.", None, 42, ""])
        with (
            patch.object(consolidator, "_chat", return_value=payload),
            patch("pms.api.services.consolidator.embedder.embed", return_value=[1.0, 0.0, 0.0, 0.0]),
        ):
            result = consolidator.run_mtm_to_ltm()
        assert result["concepts_created"] == 1  # only the valid string
