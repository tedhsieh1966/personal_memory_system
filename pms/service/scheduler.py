from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .config import get_config
from .db import get_conn

logger = logging.getLogger(__name__)

_scheduler = None


# ── Public API ───────────────────────────────────────────────────────────────

def is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def start() -> None:
    global _scheduler
    if is_running():
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning("APScheduler not installed — scheduled jobs disabled")
        return

    from . import browser_poller, consolidator

    cfg = get_config()
    stm_hours: int = cfg["consolidation"]["stm_trigger_hours"]
    mtm_cron: str = cfg["consolidation"]["mtm_schedule"]
    cron_min, cron_hr, cron_day, cron_mon, cron_dow = mtm_cron.split()
    browser_interval_min: int = cfg["ingestion"].get("browser_poll_interval_min", 30)

    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        _make_async_job("maintenance", consolidator.run_maintenance),
        trigger=IntervalTrigger(minutes=60),
        id="maintenance",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.add_job(
        _make_async_job("stm_to_mtm", consolidator.run_stm_to_mtm),
        trigger=IntervalTrigger(hours=stm_hours),
        id="stm_to_mtm",
        replace_existing=True,
        misfire_grace_time=600,
    )
    _scheduler.add_job(
        _make_async_job("mtm_to_ltm", consolidator.run_mtm_to_ltm),
        trigger=CronTrigger(
            minute=cron_min,
            hour=cron_hr,
            day=cron_day,
            month=cron_mon,
            day_of_week=cron_dow,
        ),
        id="mtm_to_ltm",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _make_async_job("browser_poll", browser_poller.poll_once),
        trigger=IntervalTrigger(minutes=browser_interval_min),
        id="browser_poll",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started (maintenance/1h, stm→mtm/%dh, mtm→ltm cron=%s, browser/%dmin)",
        stm_hours, mtm_cron, browser_interval_min,
    )


def stop() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None


def run_and_log(task: str, fn: Callable[[], Any]) -> dict:
    """Run fn synchronously, record start/end in scheduler_log, return result."""
    conn = get_conn()
    started = time.time()
    with conn:
        cur = conn.execute(
            "INSERT INTO scheduler_log (task, started_at, status) VALUES (?, ?, ?)",
            (task, started, "running"),
        )
        log_id = cur.lastrowid

    try:
        result = fn()
        status, detail = "ok", str(result)[:2000]
    except Exception as exc:
        logger.exception("Job %s raised an exception", task)
        status, detail, result = "error", str(exc)[:2000], {}

    finished = time.time()
    with conn:
        conn.execute(
            "UPDATE scheduler_log SET finished_at=?, status=?, detail=? WHERE id=?",
            (finished, status, detail, log_id),
        )
    return result if isinstance(result, dict) else {}


def get_last_run(task: str) -> datetime | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT finished_at FROM scheduler_log "
        "WHERE task=? AND status='ok' ORDER BY finished_at DESC LIMIT 1",
        (task,),
    ).fetchone()
    if row and row[0]:
        return datetime.fromtimestamp(row[0], tz=timezone.utc)
    return None


# ── Internal ─────────────────────────────────────────────────────────────────

def _make_async_job(task: str, fn: Callable) -> Callable:
    async def _job() -> None:
        await asyncio.to_thread(run_and_log, task, fn)
    _job.__name__ = f"job_{task}"
    return _job
