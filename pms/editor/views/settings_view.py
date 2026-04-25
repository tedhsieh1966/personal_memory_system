"""Settings view — edit config via POST /config."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from . import ViewBase

_FIELDS = [
    ("API Connection", None, "section", {}),
    ("Host",          ("api", "host"),                "entry",  {}),
    ("Port",          ("api", "port"),                "entry",  {}),

    ("AI Backend", None, "section", {}),
    ("Endpoint URL",  ("ai", "base_url"),             "entry",  {}),
    ("API Key",       ("ai", "api_key"),              "entry",  {"show": "*"}),
    ("Chat Model",    ("ai", "model"),                "entry",  {}),

    ("Embedding", None, "section", {}),
    ("Backend",       ("embedding", "backend"),       "combo",  {"values": ["ollama", "sentence_transformers"]}),
    ("Embed Model",   ("embedding", "model"),         "entry",  {}),
    ("Ollama URL",    ("embedding", "ollama_url"),    "entry",  {}),

    ("Memory", None, "section", {}),
    ("STM Capacity",  ("stm", "capacity"),            "entry",  {}),
    ("STM TTL (hrs)", ("stm", "ttl_hours"),           "entry",  {}),
    ("MTM Decay λ",   ("mtm", "decay_lambda"),        "entry",  {}),
    ("MTM TTL (days)",("mtm", "soft_ttl_days"),       "entry",  {}),

    ("Consolidation", None, "section", {}),
    ("STM Trigger (hrs)",   ("consolidation", "stm_trigger_hours"), "entry", {}),
    ("MTM Schedule (cron)", ("consolidation", "mtm_schedule"),      "entry", {}),

    ("Ingestion", None, "section", {}),
    ("Chrome DB Path",       ("ingestion", "browser_db_paths", "chrome"),  "entry", {}),
    ("Firefox Profiles",     ("ingestion", "browser_db_paths", "firefox"), "entry", {}),
    ("Poll Interval (min)",  ("ingestion", "browser_poll_interval_min"),   "entry", {}),
    ("Watched Dirs (;-sep)", ("ingestion", "watched_dirs"),                "entry", {}),
]


def _get_nested(d: dict, *keys: str):
    for k in keys:
        if not isinstance(d, dict):
            return ""
        d = d.get(k, "")
    return d


def _set_nested(d: dict, keys: tuple, value) -> None:
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


class SettingsView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._widgets: dict[tuple, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(hdr, text="Settings", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(
            hdr, text="Save Settings", width=120, height=30,
            fg_color="#1a7a3c", hover_color="#145e2e",
            command=self._save,
        ).pack(side="right")
        ctk.CTkButton(
            hdr, text="Refresh", width=80, height=30, command=self.refresh
        ).pack(side="right", padx=4)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 0))
        scroll.grid_columnconfigure(1, weight=1)
        self._form = scroll

        self._status_lbl = ctk.CTkLabel(
            self, text="", text_color="#aaa", font=("Arial", 12)
        )
        self._status_lbl.grid(row=2, column=0, sticky="w", padx=20, pady=(4, 12))

        self._populate_form({})

    def _populate_form(self, cfg: dict) -> None:
        for w in self._form.winfo_children():
            w.destroy()
        self._widgets.clear()

        row = 0
        for label, path, wtype, extra in _FIELDS:
            if wtype == "section":
                ctk.CTkLabel(
                    self._form, text=label,
                    font=("Arial", 13, "bold"), text_color="#5B9BD5",
                ).grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(14, 2))
                row += 1
                continue

            ctk.CTkLabel(
                self._form, text=f"{label}:", width=160, anchor="e",
                text_color="#aaa", font=("Arial", 12),
            ).grid(row=row, column=0, sticky="e", padx=(4, 8), pady=5)

            raw = ""
            if path:
                raw = _get_nested(cfg, *path)
                if isinstance(raw, list):
                    raw = ";".join(str(x) for x in raw)
                else:
                    raw = "" if raw is None else str(raw)

            if wtype == "combo":
                var = tk.StringVar(value=raw)
                widget = ctk.CTkComboBox(
                    self._form, variable=var,
                    values=extra.get("values", []),
                    width=360, font=("Arial", 13),
                )
            else:
                var = tk.StringVar(value=raw)
                widget = ctk.CTkEntry(
                    self._form, textvariable=var, width=360,
                    height=34, font=("Arial", 13),
                    show=extra.get("show", ""),
                )

            widget.grid(row=row, column=1, sticky="ew", padx=(0, 4), pady=5)
            if path:
                self._widgets[path] = var
            row += 1

    def refresh(self) -> None:
        self._status_lbl.configure(text="Loading…", text_color="#aaa")
        self._run_async(self.client.get_config, self._on_config)

    def _on_config(self, cfg: dict | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Load error: {err}", text_color="#e74c3c")
            return
        self._status_lbl.configure(text="")
        self._populate_form(cfg or {})

    def _save(self) -> None:
        updates: dict = {}
        for path, var in self._widgets.items():
            raw = var.get().strip()
            try:
                if path[-1] in ("port", "capacity", "ttl_hours", "soft_ttl_days",
                                 "stm_trigger_hours", "browser_poll_interval_min"):
                    raw = int(raw) if raw else 0
                elif path[-1] in ("decay_lambda", "min_mtm_score", "ltm_merge_cosine"):
                    raw = float(raw) if raw else 0.0
            except ValueError:
                pass
            if path[-1] == "watched_dirs" and isinstance(raw, str):
                raw = [p.strip() for p in raw.split(";") if p.strip()]
            _set_nested(updates, path, raw)

        self._status_lbl.configure(text="Saving…", text_color="#f0a500")
        self._run_async(lambda: self.client.update_config(updates), self._on_saved)

    def _on_saved(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Save failed: {err}", text_color="#e74c3c")
        else:
            self._status_lbl.configure(text="Settings saved.", text_color="#2ecc71")
