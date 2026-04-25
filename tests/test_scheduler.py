"""Tests for scheduler: run_and_log, get_last_run, start/stop."""
from __future__ import annotations

import time

import pytest

from pms.api.services import scheduler


class TestRunAndLog:
    def test_successful_job_logged_ok(self):
        result = scheduler.run_and_log("test_task", lambda: {"done": True})
        assert result == {"done": True}
        last = scheduler.get_last_run("test_task")
        assert last is not None

    def test_failed_job_logged_error(self):
        def boom():
            raise RuntimeError("intentional failure")

        result = scheduler.run_and_log("failing_task", boom)
        assert result == {}
        # Status should be 'error', so get_last_run (which filters status='ok') returns None
        assert scheduler.get_last_run("failing_task") is None

    def test_run_and_log_records_timestamps(self):
        before = time.time()
        scheduler.run_and_log("ts_task", lambda: {})
        after = time.time()
        from pms.api.db import get_conn
        conn = get_conn()
        row = conn.execute(
            "SELECT started_at, finished_at FROM scheduler_log WHERE task='ts_task'"
        ).fetchone()
        assert before <= row[0] <= after
        assert row[1] >= row[0]


class TestGetLastRun:
    def test_returns_none_when_no_runs(self):
        assert scheduler.get_last_run("never_ran") is None

    def test_returns_most_recent_run(self):
        scheduler.run_and_log("repeated", lambda: {})
        time.sleep(0.01)
        scheduler.run_and_log("repeated", lambda: {})
        last = scheduler.get_last_run("repeated")
        assert last is not None
        # Should be close to now
        import time as _t
        from datetime import timezone
        from datetime import datetime
        now = datetime.now(tz=timezone.utc)
        delta = abs((now - last).total_seconds())
        assert delta < 5


class TestIsRunning:
    def test_not_running_initially(self):
        assert scheduler.is_running() is False

    def test_running_after_start(self):
        import asyncio

        async def _run():
            scheduler.start()
            assert scheduler.is_running() is True
            scheduler.stop()

        asyncio.run(_run())

    def test_not_running_after_stop(self):
        import asyncio

        async def _run():
            scheduler.start()
            scheduler.stop()
            assert scheduler.is_running() is False

        asyncio.run(_run())

    def test_start_idempotent(self):
        import asyncio

        async def _run():
            scheduler.start()
            scheduler.start()  # should not raise
            assert scheduler.is_running() is True
            scheduler.stop()

        asyncio.run(_run())
