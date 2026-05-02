"""Shared base class and helpers for all editor views."""
from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk


class ViewBase(ctk.CTkFrame):
    """Base frame for all editor views with thread-safe async helper."""

    def __init__(self, parent: Any, client: Any, translator: Any = None, **kwargs: Any) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self.client = client
        # translator.translate bound as self.tr; falls back to identity if absent
        self.tr: Callable[[str], str] = translator.translate if translator else (lambda k: k)

    def _run_async(self, fn: Callable, on_done: Callable[[Any, Exception | None], None]) -> None:
        """Run fn in a background thread; schedule on_done(result, error) on UI thread."""
        def _target() -> None:
            try:
                result = fn()
                self.after(0, lambda r=result: on_done(r, None))
            except Exception as exc:
                self.after(0, lambda e=exc: on_done(None, e))

        threading.Thread(target=_target, daemon=True).start()

    def refresh(self) -> None:
        """Called when this panel becomes visible. Override to reload data."""

    def _add_info_row(
        self, parent: ctk.CTkFrame, row: int, label: str, attr: str, pad_bottom: int = 4
    ) -> ctk.CTkLabel:
        """LKM-style key: value row. Returns the value label (stored as self.<attr>)."""
        ctk.CTkLabel(
            parent, text=f"{label}:", anchor="e", width=140, text_color="#aaa",
            font=("Arial", 12),
        ).grid(row=row, column=0, sticky="e", padx=(12, 4), pady=(0, pad_bottom))
        lbl = ctk.CTkLabel(parent, text="—", anchor="w", font=("Arial", 12))
        lbl.grid(row=row, column=1, sticky="w", padx=(4, 12), pady=(0, pad_bottom))
        setattr(self, attr, lbl)
        return lbl


def confirm(title: str, message: str) -> bool:
    """Simple yes/no confirmation via tkinter messagebox."""
    return messagebox.askyesno(title, message)


def fmt_time(ts: str | None) -> str:
    """Format ISO timestamp to short local string."""
    if not ts:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return ts[:16] if ts else "—"
