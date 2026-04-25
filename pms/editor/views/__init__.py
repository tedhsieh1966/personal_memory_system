"""Shared base class and helpers for all editor views."""
from __future__ import annotations

import threading
from typing import Any, Callable

import customtkinter as ctk


class ViewBase(ctk.CTkFrame):
    """Base frame for all editor views with thread-safe async helper."""

    def __init__(self, parent: Any, client: Any, **kwargs: Any):
        super().__init__(parent, **kwargs)
        self.client = client

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
        """Called when this view becomes visible. Override to reload data."""


def confirm_dialog(title: str, message: str) -> bool:
    """Modal yes/no confirmation using a CTkToplevel. Returns True if confirmed."""
    result: list[bool] = [False]

    dlg = ctk.CTkToplevel()
    dlg.title(title)
    dlg.geometry("360x140")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.focus_set()

    ctk.CTkLabel(dlg, text=message, wraplength=320, justify="center").pack(
        padx=20, pady=(20, 10)
    )

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack()

    def _ok() -> None:
        result[0] = True
        dlg.destroy()

    ctk.CTkButton(btn_row, text="Confirm", command=_ok, width=110).pack(side="left", padx=6)
    ctk.CTkButton(
        btn_row, text="Cancel", command=dlg.destroy,
        fg_color="gray50", hover_color="gray40", width=110,
    ).pack(side="left", padx=6)

    dlg.wait_window()
    return result[0]


def fmt_time(ts: str | None) -> str:
    """Format ISO timestamp to short local string."""
    if not ts:
        return "—"
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return ts[:16] if ts else "—"
