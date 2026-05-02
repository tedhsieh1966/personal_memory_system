"""PMS Editor — main CustomTkinter application window (LKM-style layout)."""
from __future__ import annotations

import threading

import customtkinter as ctk

from .api_client import PMSClient
from .i18n import get_translator
from .prefs import get_language, set_language
from .views.dashboard import DashboardView
from .views.ltm_view import LTMView
from .views.log_view import LogView
from .views.mtm_view import MTMView
from .views.settings_view import SettingsView
from .views.stm_view import STMView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_CHECK_MS = 10_000


class PMSEditorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.translator = get_translator(get_language())
        self.tr = self.translator.translate

        self.title(self.tr("app.window_title"))
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.client = PMSClient()
        self._active: str | None = None
        self._nav_btns: dict[str, ctk.CTkButton] = {}

        self._nav_keys = [
            ("dashboard", "nav.dashboard"),
            ("stm",       "nav.stm"),
            ("mtm",       "nav.mtm"),
            ("ltm",       "nav.ltm"),
            ("settings",  "nav.settings"),
            ("log",       "nav.log"),
        ]

        self._build()
        self._switch_panel("dashboard")
        self.after(500, self._connect)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_panels()

    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, height=52, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        ctk.CTkLabel(
            bar, text=self.tr("app.title"), font=("Arial", 15, "bold")
        ).grid(row=0, column=0, padx=(16, 24), pady=12)

        ctk.CTkLabel(bar, text=self.tr("topbar.server_url"), text_color="#aaa").grid(
            row=0, column=1, sticky="e", padx=(0, 4)
        )
        self._url_entry = ctk.CTkEntry(
            bar, width=260, placeholder_text="http://127.0.0.1:8765"
        )
        self._url_entry.insert(0, self.client.base_url)
        self._url_entry.grid(row=0, column=2, padx=(0, 8), pady=10)
        self._url_entry.bind("<Return>", lambda _: self._connect())

        self._btn_connect = ctk.CTkButton(
            bar, text=self.tr("topbar.connect"), width=80, height=32,
            command=self._connect,
        )
        self._btn_connect.grid(row=0, column=3, padx=(0, 12))

        self._status_lbl = ctk.CTkLabel(
            bar, text=self.tr("status.not_connected"),
            text_color="#888", font=("Arial", 12),
        )
        self._status_lbl.grid(row=0, column=4, padx=(0, 20))

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        for i, (key, t_key) in enumerate(self._nav_keys):
            btn = ctk.CTkButton(
                sidebar, text=self.tr(t_key), anchor="w",
                fg_color="transparent", hover_color="#2a2d2e",
                font=("Arial", 13), height=40, corner_radius=6,
                command=lambda k=key: self._switch_panel(k),
            )
            btn.grid(
                row=i, column=0, sticky="ew",
                padx=8, pady=(8 if i == 0 else 2, 2),
            )
            self._nav_btns[key] = btn

    def _build_panels(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=1, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        tr = self.translator
        self._panels: dict[str, ctk.CTkFrame] = {
            "dashboard": DashboardView(container, self.client, translator=tr),
            "stm":       STMView(container, self.client, translator=tr),
            "mtm":       MTMView(container, self.client, translator=tr),
            "ltm":       LTMView(container, self.client, translator=tr),
            "settings":  SettingsView(container, self.client, translator=tr,
                                      on_language_change=self._on_language_change),
            "log":       LogView(container, self.client, translator=tr),
        }
        for panel in self._panels.values():
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_remove()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_panel(self, key: str) -> None:
        if self._active == key:
            return
        for k, panel in self._panels.items():
            if k == key:
                panel.grid()
            else:
                panel.grid_remove()

        for k, btn in self._nav_btns.items():
            btn.configure(fg_color="#1f538d" if k == key else "transparent")

        self._active = key
        self._panels[key].refresh()

    # ── Language change ───────────────────────────────────────────────────────

    def _on_language_change(self, language: str) -> None:
        set_language(language)
        self.translator.set_current_language(language)

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        url = self._url_entry.get().strip().rstrip("/")
        if url:
            self.client = PMSClient(url if url.startswith("http") else "http://" + url)
            for panel in self._panels.values():
                panel.client = self.client

        self._btn_connect.configure(state="disabled", text=self.tr("topbar.connecting"))
        self._status_lbl.configure(text=self.tr("status.connecting"), text_color="#f0a500")
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self) -> None:
        alive = self.client.is_alive()
        if alive:
            self.after(0, lambda: (
                self._status_lbl.configure(
                    text=f"{self.tr('status.connected_prefix')}  {self.client.base_url}",
                    text_color="#2ecc71",
                ),
                self._btn_connect.configure(state="normal", text=self.tr("topbar.connect")),
            ))
            self.after(0, lambda: self._panels[self._active].refresh() if self._active else None)
        else:
            self.after(0, lambda: (
                self._status_lbl.configure(
                    text=self.tr("status.cannot_connect"),
                    text_color="#e74c3c",
                ),
                self._btn_connect.configure(state="normal", text=self.tr("topbar.connect")),
            ))
        self.after(_CHECK_MS, self._connect_silent)

    def _connect_silent(self) -> None:
        def _check() -> None:
            alive = self.client.is_alive()
            color = "#2ecc71" if alive else "#e74c3c"
            text = (
                f"{self.tr('status.connected_prefix')}  {self.client.base_url}" if alive
                else self.tr("status.cannot_connect")
            )
            self.after(0, lambda: self._status_lbl.configure(text=text, text_color=color))
            self.after(_CHECK_MS, self._connect_silent)

        threading.Thread(target=_check, daemon=True).start()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_close(self) -> None:
        self.client.close()
        self.destroy()


def run() -> None:
    app = PMSEditorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
