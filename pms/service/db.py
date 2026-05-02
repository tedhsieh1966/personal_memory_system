from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .config import get_config

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                path = get_config()["storage"]["db_path"]
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                _init_schema(conn)
                _conn = conn
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stm_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            keywords    TEXT,
            metadata    TEXT,
            created_at  REAL    NOT NULL,
            expires_at  REAL    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_stm_expires ON stm_events(expires_at);
        CREATE INDEX IF NOT EXISTS idx_stm_created ON stm_events(created_at);

        CREATE VIRTUAL TABLE IF NOT EXISTS stm_fts
            USING fts5(content, keywords, content=stm_events, content_rowid=id);

        CREATE TRIGGER IF NOT EXISTS stm_ai AFTER INSERT ON stm_events BEGIN
            INSERT INTO stm_fts(rowid, content, keywords)
            VALUES (new.id, new.content, new.keywords);
        END;
        CREATE TRIGGER IF NOT EXISTS stm_ad AFTER DELETE ON stm_events BEGIN
            INSERT INTO stm_fts(stm_fts, rowid, content, keywords)
            VALUES ('delete', old.id, old.content, old.keywords);
        END;
        CREATE TRIGGER IF NOT EXISTS stm_au AFTER UPDATE ON stm_events BEGIN
            INSERT INTO stm_fts(stm_fts, rowid, content, keywords)
            VALUES ('delete', old.id, old.content, old.keywords);
            INSERT INTO stm_fts(rowid, content, keywords)
            VALUES (new.id, new.content, new.keywords);
        END;

        CREATE TABLE IF NOT EXISTS mtm_episodes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            summary          TEXT    NOT NULL,
            topic_tags       TEXT,
            importance_score REAL    NOT NULL DEFAULT 5.0,
            access_count     INTEGER NOT NULL DEFAULT 0,
            pinned           INTEGER NOT NULL DEFAULT 0,
            source_ids       TEXT,
            created_at       REAL    NOT NULL,
            last_accessed    REAL,
            expires_at       REAL
        );

        CREATE INDEX IF NOT EXISTS idx_mtm_score ON mtm_episodes(importance_score);
        CREATE INDEX IF NOT EXISTS idx_mtm_created ON mtm_episodes(created_at);

        CREATE VIRTUAL TABLE IF NOT EXISTS mtm_fts
            USING fts5(summary, topic_tags, content=mtm_episodes, content_rowid=id);

        CREATE TRIGGER IF NOT EXISTS mtm_ai AFTER INSERT ON mtm_episodes BEGIN
            INSERT INTO mtm_fts(rowid, summary, topic_tags)
            VALUES (new.id, new.summary, new.topic_tags);
        END;
        CREATE TRIGGER IF NOT EXISTS mtm_ad AFTER DELETE ON mtm_episodes BEGIN
            INSERT INTO mtm_fts(mtm_fts, rowid, summary, topic_tags)
            VALUES ('delete', old.id, old.summary, old.topic_tags);
        END;
        CREATE TRIGGER IF NOT EXISTS mtm_au AFTER UPDATE ON mtm_episodes BEGIN
            INSERT INTO mtm_fts(mtm_fts, rowid, summary, topic_tags)
            VALUES ('delete', old.id, old.summary, old.topic_tags);
            INSERT INTO mtm_fts(rowid, summary, topic_tags)
            VALUES (new.id, new.summary, new.topic_tags);
        END;

        CREATE TABLE IF NOT EXISTS scheduler_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task        TEXT    NOT NULL,
            started_at  REAL    NOT NULL,
            finished_at REAL,
            status      TEXT,
            detail      TEXT
        );
    """)
    conn.commit()
