"""Settings view — edit config via POST /config."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from . import ViewBase

# (section_label, config_path, widget_type, extra_kwargs)
_FIELDS = [
    # API connection
    ("API Connection", None, "section", {}),
    ("Host",          ("api", "host"),                "entry",  {}),
    ("Port",          ("api", "port"),                "entry",  {}),

    # AI backend
    ("AI Backend", None, "section", {}),
    ("Endpoint URL",  ("ai", "base_url"),             "entry",  {}),
    ("API Key",       ("ai", "api_key"),              "entry",  {"show": "*"}),
    ("Chat Model",    ("ai", "model"),                "entry",  {}),

    # Embedding
    ("Embedding", None, "section", {}),
    ("Backend",       ("embedding", "backend"),       "combo",  {"values": ["ollama", "sentence_transformers"]}),
    ("Embed Model",   ("embedding", "model"),         "entry",  {}),
    ("Ollama URL",    ("embedding", "ollama_url"),    "entry",  {}),

    # Memory
    ("Memory", None, "section", {}),
    ("STM Capacity",  ("stm", "capacity"),            "entry",  {}),
    ("STM TTL (hrs)", ("stm", "ttl_hours"),           "entry",  {}),
    ("MTM Decay λ",   ("mtm", "decay_lambda"),        "entry",  {}),
    ("MTM TTL (days)",("mtm", "soft_ttl_days"),       "entry",  {}),

    # Consolidation
    ("Consolidation", None, "section", {}),
    ("STM Trigger (hrs)", ("consolidation", "stm_trigger_hours"),  "entry", {}),
    ("MTM Schedule (cron)",("consolidation", "mtm_schedule"),      "entry", {}),

    # Ingestion
    ("Ingestion", None, "section", {}),
    ("Chrome DB Path",   ("ingestion", "browser_db_paths", "chrome"),  "entry", {}),
    ("Firefox Profiles", ("ingestion", "browser_db_paths", "firefox"), "entry", {}),
    ("Poll Interval (min)",("ingestion", "browser_poll_interval_min"), "entry", {}),
    ("Watched Dirs (;-sep)", ("ingestion", "watched_dirs"),            "entry", {}),
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
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(hdr, text="Settings",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="Refresh", width=80, command=self.refresh).pack(side="right", padx=4)
        ctk.CTkButton(hdr, text="Save Settings", width=110, command=self._save).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 0))
        scroll.grid_columnconfigure(1, weight=1)
        self._form = scroll

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="gray60")
        self._status_lbl.grid(row=2, column=0, sticky="w", padx=16, pady=(4, 8))

        self._populate_form({})

    def _populate_form(self, cfg: dict) -> None:
        for w in self._form.winfo_children():
            w.destroy()
        self._widgets.clear()

        row = 0
        for label, path, wtype, extra in _FIELDS:
            if wtype == "section":
                lbl = ctk.CTkLabel(self._form, text=label,
                                   font=ctk.CTkFont(weight="bold"), text_color="#5B9BD5")
                lbl.grid(row=row, column=0, columnspan=2, sticky="w",
                         padx=4, pady=(14, 2))
                row += 1
                continue

            ctk.CTkLabel(self._form, text=label, width=160, anchor="w").grid(
                row=row, column=0, sticky="w", padx=4, pady=3
            )

            if path:
                raw = _get_nested(cfg, *path)
                if isinstance(raw, list):
                    raw = ";".join(str(x) for x in raw)
                else:
                    raw = "" if raw is None else str(raw)
            else:
                raw = ""

            if wtype == "combo":
                var = tk.StringVar(value=raw)
                widget = ctk.CTkComboBox(self._form, variable=var,
                                         values=extra.get("values", []), width=320)
            else:
                var = tk.StringVar(value=raw)
                widget = ctk.CTkEntry(self._form, textvariable=var, width=320,
                                      show=extra.get("show", ""))

            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            if path:
                self._widgets[path] = var
            row += 1

    def refresh(self) -> None:
        self._status_lbl.configure(text="Loading…")
        self._run_async(self.client.get_config, self._on_config)

    def _on_config(self, cfg: dict | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Load error: {err}")
            return
        self._status_lbl.configure(text="")
        self._populate_form(cfg or {})

    def _save(self) -> None:
        updates: dict = {}
        for path, var in self._widgets.items():
            raw = var.get().strip()
            # Type-cast known numeric fields
            try:
                if path[-1] in ("port", "capacity", "ttl_hours", "soft_ttl_days",
                                 "stm_trigger_hours", "browser_poll_interval_min"):
                    raw = int(raw) if raw else 0
                elif path[-1] in ("decay_lambda", "min_mtm_score", "ltm_merge_cosine"):
                    raw = float(raw) if raw else 0.0
            except ValueError:
                pass
            # watched_dirs comes in as semicolon-separated string
            if path[-1] == "watched_dirs" and isinstance(raw, str):
                raw = [p.strip() for p in raw.split(";") if p.strip()]
            _set_nested(updates, path, raw)

        self._run_async(lambda: self.client.update_config(updates), self._on_saved)

    def _on_saved(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Save failed: {err}")
        else:
            self._status_lbl.configure(text="Settings saved.")
