from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .config import get_config

# One sqlite3.Connection per thread. Sharing a single connection across the
# threads that asyncio.to_thread spawns produces sporadic
# "sqlite3.InterfaceError: bad parameter or other API misuse" errors, because
# Python's sqlite3 driver does not serialise concurrent execute() on a shared
# connection. WAL mode (set per-connection below) coordinates writers at the
# database-file level, so multiple connections to the same DB are safe.

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def get_conn() -> sqlite3.Connection:
    """Return a thread-local sqlite3.Connection, creating it on first call."""
    global _initialized

    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn

    path = get_config()["storage"]["db_path"]

    # Schema init runs exactly once across all threads; subsequent connections
    # just open the already-initialised file.
    with _init_lock:
        if not _initialized:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            init_conn = sqlite3.connect(path)
            init_conn.row_factory = sqlite3.Row
            init_conn.execute("PRAGMA journal_mode=WAL")
            init_conn.execute("PRAGMA foreign_keys=ON")
            _init_schema(init_conn)
            init_conn.close()
            _initialized = True

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # journal_mode=WAL is persisted in the DB header, but PRAGMA foreign_keys
    # is per-connection and must be set every time.
    conn.execute("PRAGMA foreign_keys=ON")
    _local.conn = conn
    return conn


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
