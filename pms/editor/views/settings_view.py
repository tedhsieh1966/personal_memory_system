"""Settings view — edit config via POST /config, plus language selection."""
from __future__ import annotations

import tkinter as tk
from typing import Callable
import customtkinter as ctk

from . import ViewBase

# (display_key, config_path, widget_type, extra, translation_key)
_FIELDS = [
    ("settings.section_api",      None,                                               "section", {},                                                    "settings.section_api"),
    ("settings.field_host",       ("api", "host"),                                    "entry",   {},                                                    "settings.field_host"),
    ("settings.field_port",       ("api", "port"),                                    "entry",   {},                                                    "settings.field_port"),

    ("settings.section_ai",       None,                                               "section", {},                                                    "settings.section_ai"),
    ("settings.field_endpoint_url",("ai_backend", "local", "base_url"),              "entry",   {},                                                    "settings.field_endpoint_url"),
    ("settings.field_api_key",    ("ai_backend", "local", "api_key"),                "entry",   {"show": "*"},                                         "settings.field_api_key"),
    ("settings.field_chat_model", ("ai_backend", "local", "model"),                  "entry",   {},                                                    "settings.field_chat_model"),

    ("settings.section_embedding",None,                                               "section", {},                                                    "settings.section_embedding"),
    ("settings.field_provider",   ("embedding", "provider"),                         "combo",   {"values": ["ollama", "sentence_transformers"]},       "settings.field_provider"),
    ("settings.field_embed_model",("embedding", "model"),                            "entry",   {},                                                    "settings.field_embed_model"),
    ("settings.field_ollama_url", ("embedding", "ollama_url"),                       "entry",   {},                                                    "settings.field_ollama_url"),

    ("settings.section_memory",   None,                                               "section", {},                                                    "settings.section_memory"),
    ("settings.field_stm_capacity",("memory", "stm_capacity"),                       "entry",   {},                                                    "settings.field_stm_capacity"),
    ("settings.field_stm_ttl_hrs",("memory", "stm_ttl_hours"),                       "entry",   {},                                                    "settings.field_stm_ttl_hrs"),
    ("settings.field_mtm_decay",  ("memory", "mtm_decay_lambda"),                    "entry",   {},                                                    "settings.field_mtm_decay"),
    ("settings.field_mtm_ttl_days",("memory", "mtm_ttl_days"),                       "entry",   {},                                                    "settings.field_mtm_ttl_days"),

    ("settings.section_consolidation",None,                                           "section", {},                                                    "settings.section_consolidation"),
    ("settings.field_stm_trigger",("consolidation", "stm_trigger_hours"),            "entry",   {},                                                    "settings.field_stm_trigger"),
    ("settings.field_mtm_schedule",("consolidation", "mtm_schedule"),                "entry",   {},                                                    "settings.field_mtm_schedule"),

    ("settings.section_ingestion",None,                                               "section", {},                                                    "settings.section_ingestion"),
    ("settings.field_chrome_db",  ("ingestion", "browser_db_paths", "chrome"),       "entry",   {},                                                    "settings.field_chrome_db"),
    ("settings.field_firefox",    ("ingestion", "browser_db_paths", "firefox"),      "entry",   {},                                                    "settings.field_firefox"),
    ("settings.field_poll_interval",("ingestion", "browser_poll_interval_min"),      "entry",   {},                                                    "settings.field_poll_interval"),
    ("settings.field_watched_dirs",("ingestion", "watched_dirs"),                    "entry",   {},                                                    "settings.field_watched_dirs"),
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
    def __init__(self, parent, client, on_language_change: Callable[[str], None] | None = None, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._widgets: dict[tuple, tk.Variable] = {}
        self._on_language_change = on_language_change
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(hdr, text=self.tr("settings.title"), font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(
            hdr, text=self.tr("settings.save"), width=120, height=30,
            fg_color="#1a7a3c", hover_color="#145e2e",
            command=self._save,
        ).pack(side="right")
        ctk.CTkButton(
            hdr, text=self.tr("common.refresh"), width=80, height=30, command=self.refresh
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

        # ── Appearance section (language picker) ──────────────────────────
        ctk.CTkLabel(
            self._form, text=self.tr("settings.section_appearance"),
            font=("Arial", 13, "bold"), text_color="#5B9BD5",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(14, 2))
        row += 1

        ctk.CTkLabel(
            self._form, text=f"{self.tr('settings.language')}:",
            width=160, anchor="e", text_color="#aaa", font=("Arial", 12),
        ).grid(row=row, column=0, sticky="e", padx=(4, 8), pady=5)

        from pms.editor.i18n import get_translator
        _tmp_tr = get_translator()
        available_langs = _tmp_tr.get_languages()
        current_lang = self.tr.__self__.current_language if hasattr(self.tr, "__self__") else available_langs[0]
        self._lang_var = tk.StringVar(value=current_lang)
        lang_combo = ctk.CTkComboBox(
            self._form, variable=self._lang_var,
            values=available_langs, width=360, font=("Arial", 13),
            command=self._on_lang_selected,
        )
        lang_combo.grid(row=row, column=1, sticky="ew", padx=(0, 4), pady=5)
        row += 1

        self._restart_lbl = ctk.CTkLabel(
            self._form, text="", text_color="#f0a500", font=("Arial", 12), anchor="w",
        )
        self._restart_lbl.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        row += 1

        # ── Server config fields ──────────────────────────────────────────
        for _, path, wtype, extra, t_key in _FIELDS:
            label = self.tr(t_key)
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

    def _on_lang_selected(self, language: str) -> None:
        self._restart_lbl.configure(text=self.tr("settings.restart_note"))
        if self._on_language_change:
            self._on_language_change(language)

    def refresh(self) -> None:
        self._status_lbl.configure(text=self.tr("common.loading"), text_color="#aaa")
        self._run_async(self.client.get_config, self._on_config)

    def _on_config(self, cfg: dict | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('settings.load_error')}: {err}", text_color="#e74c3c"
            )
            return
        self._status_lbl.configure(text="")
        self._populate_form(cfg or {})

    def _save(self) -> None:
        updates: dict = {}
        for path, var in self._widgets.items():
            raw = var.get().strip()
            try:
                if path[-1] in ("port", "stm_capacity", "stm_ttl_hours", "mtm_ttl_days",
                                 "stm_trigger_hours", "browser_poll_interval_min"):
                    raw = int(raw) if raw else 0
                elif path[-1] in ("mtm_decay_lambda", "min_mtm_score", "ltm_merge_cosine"):
                    raw = float(raw) if raw else 0.0
            except ValueError:
                pass
            if path[-1] == "watched_dirs" and isinstance(raw, str):
                raw = [p.strip() for p in raw.split(";") if p.strip()]
            _set_nested(updates, path, raw)

        self._status_lbl.configure(text=self.tr("settings.saving"), text_color="#f0a500")
        self._run_async(lambda: self.client.update_config(updates), self._on_saved)

    def _on_saved(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('settings.save_failed')}: {err}", text_color="#e74c3c"
            )
        else:
            self._status_lbl.configure(text=self.tr("settings.saved"), text_color="#2ecc71")
