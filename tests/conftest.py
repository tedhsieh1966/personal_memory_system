"""Shared fixtures: isolated temp DB + config for every test."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """
    Each test gets its own temp directory with a fresh config.yaml.
    Module-level singletons (db conn, ltm table) are reset between tests.
    """
    # Write a minimal config pointing at temp paths
    cfg = {
        "api": {"host": "127.0.0.1", "port": 8765},
        "storage": {
            "db_path": str(tmp_path / "pms.db"),
            "ltm_path": str(tmp_path / "pms_ltm"),
        },
        "memory": {
            "stm_ttl_hours": 12,
            "stm_capacity": 10,          # small for capacity tests
            "mtm_ttl_days": 21,
            "mtm_decay_lambda": 0.05,
            "mtm_score_threshold": 1.0,
            "ltm_merge_cosine": 0.95,
        },
        "consolidation": {
            "stm_trigger_hours": 6,
            "stm_trigger_pct": 0.80,
            "mtm_schedule": "0 2 * * 0",
        },
        "embedding": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "ollama_url": "http://localhost:11434",
            "dim": 4,                    # tiny dim for LTM tests
        },
        "ai_backend": {
            "provider": "local",
            "local": {"base_url": "http://localhost:11434/v1", "api_key": "ollama", "model": "test"},
            "cloud": {"base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o-mini"},
        },
        "ingestion": {
            "browser_db_paths": {},
            "browser_poll_interval_min": 30,
            "watched_dirs": [],
            "watched_extensions": [],
        },
    }
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))

    monkeypatch.setenv("PMS_CONFIG", str(cfg_path))

    # Reset all module-level singletons so each test starts fresh
    import pms.api.config as _cfg_mod
    import pms.api.db as _db_mod
    import pms.api.services.ltm as _ltm_mod

    _cfg_mod._config = None
    _db_mod._conn = None
    _ltm_mod._db = None
    _ltm_mod._table = None

    yield tmp_path
