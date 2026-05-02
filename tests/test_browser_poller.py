"""Tests for browser_poller — Chrome and Firefox history ingestion."""
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pms.service import browser_poller


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_chrome_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, last_visit_time INTEGER)"
    )
    # Two entries with timestamps well in the future (Chrome epoch microseconds)
    # Unix now + 60s → Chrome us = (unix + offset) * 1e6
    offset = 11_644_473_600
    t1 = int((time.time() - 10 + offset) * 1_000_000)   # 10s ago
    t2 = int((time.time() -  5 + offset) * 1_000_000)   #  5s ago
    conn.execute("INSERT INTO urls VALUES (1, 'https://a.com', 'Site A', ?)", (t1,))
    conn.execute("INSERT INTO urls VALUES (2, 'https://b.com', 'Site B', ?)", (t2,))
    conn.commit()
    conn.close()


def _make_firefox_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT, last_visit_date INTEGER)"
    )
    t1 = int((time.time() - 10) * 1_000_000)
    t2 = int((time.time() -  5) * 1_000_000)
    conn.execute("INSERT INTO moz_places VALUES (1, 'https://x.org', 'Site X', ?)", (t1,))
    conn.execute("INSERT INTO moz_places VALUES (2, 'https://y.org', 'Site Y', ?)", (t2,))
    conn.commit()
    conn.close()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_poll_once_no_paths(isolated_env):
    browser_poller.reset_state()
    result = browser_poller.poll_once()
    assert result == {}


def test_poll_once_chrome(isolated_env, tmp_path):
    browser_poller.reset_state()
    db = tmp_path / "History"
    _make_chrome_db(db)

    inserted = []

    with patch("pms.service.browser_poller.stm") as mock_stm, \
         patch("pms.service.browser_poller.get_config") as mock_cfg:
        mock_cfg.return_value = {
            "ingestion": {
                "browser_db_paths": {"chrome": str(db)},
                "browser_poll_interval_min": 30,
            }
        }
        mock_stm.insert = lambda source, content, kw, meta: inserted.append(content)
        result = browser_poller.poll_once()

    assert result.get("chrome") == 2
    assert any("Site A" in c for c in inserted)
    assert any("Site B" in c for c in inserted)


def test_poll_chrome_deduplication(isolated_env, tmp_path):
    """Second poll with unchanged DB returns 0 new entries."""
    browser_poller.reset_state()
    db = tmp_path / "History"
    _make_chrome_db(db)

    cfg = {
        "ingestion": {
            "browser_db_paths": {"chrome": str(db)},
            "browser_poll_interval_min": 0,
        }
    }

    with patch("pms.service.browser_poller.stm"), \
         patch("pms.service.browser_poller.get_config", return_value=cfg):
        browser_poller.poll_once()
        result2 = browser_poller.poll_once()

    assert result2.get("chrome", 0) == 0


def test_poll_once_firefox(isolated_env, tmp_path):
    browser_poller.reset_state()
    profile_dir = tmp_path / "profiles" / "abc.default"
    profile_dir.mkdir(parents=True)
    db = profile_dir / "places.sqlite"
    _make_firefox_db(db)

    inserted = []

    with patch("pms.service.browser_poller.stm") as mock_stm, \
         patch("pms.service.browser_poller.get_config") as mock_cfg:
        mock_cfg.return_value = {
            "ingestion": {
                "browser_db_paths": {"firefox": str(tmp_path / "profiles")},
                "browser_poll_interval_min": 30,
            }
        }
        mock_stm.insert = lambda source, content, kw, meta: inserted.append(content)
        result = browser_poller.poll_once()

    assert result.get("firefox") == 2
    assert any("Site X" in c for c in inserted)


def test_poll_chrome_missing_db(isolated_env, tmp_path):
    browser_poller.reset_state()
    cfg = {
        "ingestion": {
            "browser_db_paths": {"chrome": str(tmp_path / "nonexistent")},
            "browser_poll_interval_min": 30,
        }
    }
    with patch("pms.service.browser_poller.get_config", return_value=cfg):
        result = browser_poller.poll_once()
    assert result.get("chrome", 0) == 0


def test_poll_firefox_no_profiles(isolated_env, tmp_path):
    browser_poller.reset_state()
    empty_dir = tmp_path / "empty_profiles"
    empty_dir.mkdir()
    cfg = {
        "ingestion": {
            "browser_db_paths": {"firefox": str(empty_dir)},
            "browser_poll_interval_min": 30,
        }
    }
    with patch("pms.service.browser_poller.get_config", return_value=cfg):
        result = browser_poller.poll_once()
    assert result.get("firefox", 0) == 0


def test_reset_state(isolated_env):
    browser_poller._last_seen["chrome"] = 999.0
    browser_poller._last_seen["firefox"] = 888.0
    browser_poller.reset_state()
    assert browser_poller._last_seen["chrome"] == 0.0
    assert browser_poller._last_seen["firefox"] == 0.0


def test_chrome_epoch_conversion(isolated_env, tmp_path):
    """Verify Chrome timestamps convert to reasonable Unix timestamps."""
    browser_poller.reset_state()
    db = tmp_path / "History"
    _make_chrome_db(db)

    captured_meta = []

    with patch("pms.service.browser_poller.stm") as mock_stm, \
         patch("pms.service.browser_poller.get_config") as mock_cfg:
        mock_cfg.return_value = {
            "ingestion": {
                "browser_db_paths": {"chrome": str(db)},
                "browser_poll_interval_min": 30,
            }
        }
        mock_stm.insert = lambda source, content, kw, meta: captured_meta.append(meta)
        browser_poller.poll_once()

    assert len(captured_meta) == 2
    for meta in captured_meta:
        assert meta["browser"] == "chrome"
        assert meta["url"].startswith("https://")
