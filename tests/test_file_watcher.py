"""Tests for file_watcher — watchdog-based file system monitoring."""
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pms.service import file_watcher
from pms.service.file_watcher import _PMSHandler, read_snippet


# ── read_snippet ──────────────────────────────────────────────────────────────

def test_read_snippet_text_file(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Hello world", encoding="utf-8")
    result = read_snippet(f)
    assert result == "notes.txt: Hello world"


def test_read_snippet_truncates(tmp_path):
    f = tmp_path / "big.md"
    f.write_text("x" * 500, encoding="utf-8")
    result = read_snippet(f, max_chars=10)
    assert result == "big.md: " + "x" * 10


def test_read_snippet_binary_extension(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n")
    result = read_snippet(f)
    assert result == "File: image.png"


def test_read_snippet_missing_file(tmp_path):
    f = tmp_path / "missing.txt"
    result = read_snippet(f)
    assert result == "File: missing.txt"


def test_read_snippet_python_file(tmp_path):
    f = tmp_path / "script.py"
    f.write_text("import os\nprint('hi')", encoding="utf-8")
    result = read_snippet(f)
    assert "script.py" in result
    assert "import os" in result


# ── _PMSHandler ───────────────────────────────────────────────────────────────

def test_handler_ignores_directory_event(tmp_path):
    handler = _PMSHandler(set())

    class FakeEvent:
        is_directory = True
        src_path = str(tmp_path)

    with patch("pms.service.file_watcher.stm") as mock_stm:
        from watchdog.events import FileCreatedEvent
        evt = FileCreatedEvent(str(tmp_path))
        # is_directory is False for FileCreatedEvent; manually override to test guard
        evt.is_directory = True
        handler.dispatch(evt)
        mock_stm.insert.assert_not_called()


def test_handler_ingests_file(tmp_path):
    handler = _PMSHandler(set())
    f = tmp_path / "note.txt"
    f.write_text("Some content", encoding="utf-8")

    file_watcher._last_ingest.clear()

    with patch("pms.service.file_watcher.stm") as mock_stm:
        from watchdog.events import FileCreatedEvent
        handler.dispatch(FileCreatedEvent(str(f)))
        mock_stm.insert.assert_called_once()
        args = mock_stm.insert.call_args[0]
        assert args[0] == "file"
        assert "note.txt" in args[1]


def test_handler_extension_filter(tmp_path):
    handler = _PMSHandler({".md"})   # only .md files
    f = tmp_path / "data.csv"
    f.write_text("a,b,c", encoding="utf-8")

    file_watcher._last_ingest.clear()

    with patch("pms.service.file_watcher.stm") as mock_stm:
        from watchdog.events import FileCreatedEvent
        handler.dispatch(FileCreatedEvent(str(f)))
        mock_stm.insert.assert_not_called()


def test_handler_debounce(tmp_path):
    handler = _PMSHandler(set())
    f = tmp_path / "log.txt"
    f.write_text("line1", encoding="utf-8")

    file_watcher._last_ingest.clear()

    with patch("pms.service.file_watcher.stm") as mock_stm:
        from watchdog.events import FileModifiedEvent
        handler.dispatch(FileModifiedEvent(str(f)))
        handler.dispatch(FileModifiedEvent(str(f)))   # within debounce window
        assert mock_stm.insert.call_count == 1


# ── start / stop ──────────────────────────────────────────────────────────────

def test_start_no_watched_dirs(isolated_env):
    file_watcher._observer = None
    file_watcher.start()
    assert file_watcher._observer is None


def test_start_nonexistent_dir(isolated_env, tmp_path, monkeypatch):
    from pms.service.config import get_config
    cfg = get_config()
    cfg["ingestion"]["watched_dirs"] = [str(tmp_path / "no_such_dir")]
    cfg["ingestion"]["watched_extensions"] = [".txt"]

    file_watcher._observer = None
    try:
        file_watcher.start()
        # no dirs added → observer not started
        assert file_watcher._observer is None or not file_watcher._observer.is_alive()
    finally:
        file_watcher.stop()


def test_stop_when_not_started(isolated_env):
    file_watcher._observer = None
    file_watcher.stop()   # should not raise


def test_start_and_stop(isolated_env, tmp_path, monkeypatch):
    from pms.service.config import get_config
    cfg = get_config()
    cfg["ingestion"]["watched_dirs"] = [str(tmp_path)]
    cfg["ingestion"]["watched_extensions"] = []

    file_watcher._observer = None
    try:
        file_watcher.start()
        assert file_watcher._observer is not None
        assert file_watcher._observer.is_alive()
    finally:
        file_watcher.stop()
    assert file_watcher._observer is None
