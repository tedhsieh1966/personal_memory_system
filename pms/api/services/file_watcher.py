"""File system watcher — monitors configured directories via watchdog."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from ..config import get_config
from . import stm

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".rst", ".csv",
}

_DEBOUNCE_SECONDS = 5.0   # ignore repeated events on the same path within this window

_observer = None
_last_ingest: dict[str, float] = {}   # path → last ingest Unix timestamp


def start() -> None:
    """Start the watchdog Observer for all configured watched_dirs."""
    global _observer
    if _observer is not None and _observer.is_alive():
        return

    cfg = get_config()
    watched_dirs: list[str] = cfg["ingestion"].get("watched_dirs", [])
    extensions: set[str] = set(cfg["ingestion"].get("watched_extensions", []))

    if not watched_dirs:
        logger.info("No watched_dirs configured — file watcher not started")
        return

    try:
        from watchdog.observers import Observer
        _observer = Observer()
        handler = _PMSHandler(extensions)
        added = 0
        for d in watched_dirs:
            p = Path(d)
            if p.is_dir():
                _observer.schedule(handler, str(p), recursive=True)
                logger.info("File watcher: monitoring %s", p)
                added += 1
            else:
                logger.warning("File watcher: directory not found — %s", p)
        if added:
            _observer.start()
    except ImportError:
        logger.warning("watchdog not installed — file watcher disabled")
    except Exception as exc:
        logger.error("File watcher start error: %s", exc)


def stop() -> None:
    global _observer
    if _observer is not None:
        try:
            _observer.stop()
            _observer.join(timeout=5)
        except Exception:
            pass
        _observer = None
        logger.info("File watcher stopped")


def read_snippet(path: Path, max_chars: int = 200) -> str:
    """Return 'filename: <first max_chars chars>' for text files, or 'File: filename' for binary."""
    try:
        if path.suffix.lower() in _TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
            return f"{path.name}: {text}".strip()
        return f"File: {path.name}"
    except Exception:
        return f"File: {path.name}"


# ── Watchdog handler ──────────────────────────────────────────────────────────

class _PMSHandler:
    def __init__(self, extensions: set[str]) -> None:
        self._extensions = extensions

    # watchdog calls these synchronously in the Observer thread
    def dispatch(self, event) -> None:
        from watchdog.events import FileCreatedEvent, FileModifiedEvent
        if isinstance(event, (FileCreatedEvent, FileModifiedEvent)):
            if not event.is_directory:
                self._handle(event.src_path)

    def _handle(self, path_str: str) -> None:
        path = Path(path_str)
        if self._extensions and path.suffix.lower() not in self._extensions:
            return
        now = time.time()
        if now - _last_ingest.get(path_str, 0.0) < _DEBOUNCE_SECONDS:
            return
        _last_ingest[path_str] = now
        content = read_snippet(path)
        stm.insert("file", content, None, {"path": path_str})
        logger.debug("File ingested: %s", path.name)
