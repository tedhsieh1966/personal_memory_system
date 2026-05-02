"""Log view — tail of pms_server.log with auto-refresh and level filter."""
from __future__ import annotations

import os
import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path

import customtkinter as ctk

from . import ViewBase

_DEFAULT_LOG = "pms_server.log"
_TAIL_LINES  = 300
_REFRESH_MS  = 2000


class LogView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._auto_refresh = False
        self._after_id: str | None = None
        self._all_lines: list[str] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Toolbar ────────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 6))

        ctk.CTkLabel(toolbar, text="Log", font=("Arial", 16, "bold")).pack(side="left")

        ctk.CTkButton(
            toolbar, text="Refresh", width=80, height=30, command=self._load_log
        ).pack(side="left", padx=(16, 4))

        ctk.CTkButton(
            toolbar, text="Browse…", width=80, height=30, command=self._browse_log
        ).pack(side="left", padx=4)

        self._auto_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(
            toolbar, text="Auto-refresh", variable=self._auto_var,
            font=("Arial", 12), command=self._toggle_auto,
        ).pack(side="left", padx=12)

        ctk.CTkLabel(toolbar, text="Filter:", font=("Arial", 12)).pack(side="left", padx=(12, 4))
        self._level_var = tk.StringVar(value="ALL")
        ctk.CTkComboBox(
            toolbar, variable=self._level_var,
            values=["ALL", "INFO", "WARNING", "ERROR", "DEBUG"],
            width=100, font=("Arial", 12),
            command=lambda _: self._apply_filter(),
        ).pack(side="left")

        # ── Path row ───────────────────────────────────────────────────────
        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 4))
        ctk.CTkLabel(path_row, text="File:", font=("Arial", 12), text_color="#aaa").pack(side="left")
        self._path_var = tk.StringVar(value=str(Path.cwd() / _DEFAULT_LOG))
        ctk.CTkEntry(
            path_row, textvariable=self._path_var, width=480, height=30, font=("Arial", 12),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            path_row, text="Load", width=60, height=30, font=("Arial", 12),
            command=self._load_log,
        ).pack(side="left")

        # ── Textbox ────────────────────────────────────────────────────────
        self._textbox = ctk.CTkTextbox(
            self, state="disabled", font=("Consolas", 11),
        )
        self._textbox.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))

        self._status_lbl = ctk.CTkLabel(
            self, text="", text_color="#aaa", font=("Arial", 12),
        )
        self._status_lbl.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 12))

    def refresh(self) -> None:
        self._load_log()

    def _browse_log(self) -> None:
        path = fd.askopenfilename(
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if path:
            self._path_var.set(path)
            self._load_log()

    def _load_log(self) -> None:
        path = self._path_var.get().strip()
        if not path or not os.path.isfile(path):
            self._set_text(f"[File not found: {path}]")
            self._status_lbl.configure(text=f"Not found: {path}", text_color="#e74c3c")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            self._all_lines = lines[-_TAIL_LINES:]
            self._apply_filter()
            self._status_lbl.configure(
                text=f"{len(self._all_lines)} lines", text_color="#aaa"
            )
        except Exception as exc:
            self._set_text(f"[Read error: {exc}]")
            self._status_lbl.configure(text=f"Read error: {exc}", text_color="#e74c3c")

    def _apply_filter(self) -> None:
        level = self._level_var.get()
        filtered = (
            self._all_lines if level == "ALL"
            else [ln for ln in self._all_lines if level in ln]
        )
        self._set_text("".join(filtered))

    def _set_text(self, text: str) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("end", text)
        self._textbox.configure(state="disabled")
        self._textbox.see("end")

    def _toggle_auto(self) -> None:
        self._auto_refresh = self._auto_var.get()
        if self._auto_refresh:
            self._schedule_refresh()
        elif self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _schedule_refresh(self) -> None:
        if not self._auto_refresh:
            return
        self._load_log()
        self._after_id = self.after(_REFRESH_MS, self._schedule_refresh)

    def destroy(self) -> None:
        self._auto_refresh = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()
