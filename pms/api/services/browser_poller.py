"""Browser history poller — Chrome and Firefox SQLite history ingestion."""
from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from ..config import get_config
from . import stm

logger = logging.getLogger(__name__)

# Chrome stores timestamps as microseconds since 1601-01-01 (Windows epoch).
# There are 11 644 473 600 seconds between 1601-01-01 and 1970-01-01.
_CHROME_EPOCH_OFFSET_US = 11_644_473_600 * 1_000_000

# Per-browser last-seen Unix timestamp (seconds). 0.0 = not yet initialised.
_last_seen: dict[str, float] = {"chrome": 0.0, "firefox": 0.0}


def poll_once() -> dict:
    """Ingest new browser history events since the last poll. Returns counts per browser."""
    cfg = get_config()
    paths = cfg["ingestion"].get("browser_db_paths", {})
    interval_s = cfg["ingestion"].get("browser_poll_interval_min", 30) * 60

    result: dict[str, int] = {}

    chrome_path = paths.get("chrome", "")
    if chrome_path:
        result["chrome"] = _poll_chrome(chrome_path, interval_s)

    firefox_path = paths.get("firefox", "")
    if firefox_path:
        result["firefox"] = _poll_firefox(firefox_path, interval_s)

    return result


# ── Chrome ───────────────────────────────────────────────────────────────────

def _poll_chrome(db_path: str, interval_s: float) -> int:
    path = Path(db_path)
    if not path.exists():
        return 0

    # Initialise cutoff to one poll interval ago on first run
    if _last_seen["chrome"] == 0.0:
        _last_seen["chrome"] = time.time() - interval_s

    cutoff_chrome_us = (_last_seen["chrome"] + 11_644_473_600) * 1_000_000

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        shutil.copy2(path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT url, title, last_visit_time FROM urls "
            "WHERE last_visit_time > ? ORDER BY last_visit_time ASC LIMIT 200",
            (cutoff_chrome_us,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.debug("Chrome poll error: %s", exc)
        return 0
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    max_ts = _last_seen["chrome"]
    count = 0
    for row in rows:
        unix_ts = row["last_visit_time"] / 1_000_000 - 11_644_473_600
        title = (row["title"] or "").strip()
        url = row["url"] or ""
        content = f"{title} {url}".strip()[:500]
        if not content:
            continue
        stm.insert("browser", content, None, {"url": url, "title": title, "browser": "chrome"})
        max_ts = max(max_ts, unix_ts)
        count += 1

    _last_seen["chrome"] = max_ts
    return count


# ── Firefox ──────────────────────────────────────────────────────────────────

def _poll_firefox(profiles_base: str, interval_s: float) -> int:
    base = Path(profiles_base)
    if not base.exists():
        return 0

    if _last_seen["firefox"] == 0.0:
        _last_seen["firefox"] = time.time() - interval_s

    cutoff_us = _last_seen["firefox"] * 1_000_000

    # Pick the most recently modified places.sqlite across all profiles
    candidates = sorted(base.rglob("places.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return 0

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    max_ts = _last_seen["firefox"]
    count = 0

    try:
        shutil.copy2(candidates[0], tmp.name)
        conn = sqlite3.connect(tmp.name)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT url, title, last_visit_date FROM moz_places "
            "WHERE last_visit_date > ? AND last_visit_date IS NOT NULL "
            "ORDER BY last_visit_date ASC LIMIT 200",
            (cutoff_us,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.debug("Firefox poll error: %s", exc)
        return 0
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    for row in rows:
        unix_ts = row["last_visit_date"] / 1_000_000
        title = (row["title"] or "").strip()
        url = row["url"] or ""
        content = f"{title} {url}".strip()[:500]
        if not content:
            continue
        stm.insert("browser", content, None, {"url": url, "title": title, "browser": "firefox"})
        max_ts = max(max_ts, unix_ts)
        count += 1

    _last_seen["firefox"] = max_ts
    return count


# ── State reset (used by tests) ───────────────────────────────────────────────

def reset_state() -> None:
    _last_seen["chrome"] = 0.0
    _last_seen["firefox"] = 0.0
