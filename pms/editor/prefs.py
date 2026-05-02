"""Editor user preferences — stored in %APPDATA%/pms/editor_prefs.json."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _prefs_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    return Path(appdata) / "pms" / "editor_prefs.json"


def load_prefs() -> dict:
    path = _prefs_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_prefs(prefs: dict) -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


def get_language() -> str | None:
    return load_prefs().get("language")


def set_language(language: str) -> None:
    prefs = load_prefs()
    prefs["language"] = language
    save_prefs(prefs)
