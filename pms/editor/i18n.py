"""i18n helpers for the PMS editor — thin wrapper around LanguageTranslator."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from py_libraries.LanguageOp import LanguageTranslator, get_current_input_language


def _xlsx_path() -> str:
    """Resolve languages.xlsx whether running from source or PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = str(Path(__file__).parent)
    return os.path.join(base, "languages.xlsx")


def get_translator(saved_language: str | None = None) -> LanguageTranslator:
    """Return a ready-to-use LanguageTranslator with current_language set.

    Resolution order:
    1. saved_language (from editor_prefs.json)
    2. System input language (detected via LanguageOp)
    3. First column in the xlsx (English)
    """
    translator = LanguageTranslator(_xlsx_path())
    available = translator.get_languages()

    if saved_language and saved_language in available:
        translator.set_current_language(saved_language)
        return translator

    sys_lang = get_current_input_language().get("language_name", "")
    if sys_lang in available:
        translator.set_current_language(sys_lang)
    else:
        translator.set_current_language(available[0])

    return translator
