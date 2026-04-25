"""PMS Editor — main CustomTkinter application window (LKM-style layout)."""
from __future__ import annotations

import threading

import customtkinter as ctk

from .api_client import PMSClient
from .views.dashboard import DashboardView
from .views.ltm_view import LTMView
from .views.log_view import LogView
from .views.mtm_view import MTMView
from .views.settings_view import SettingsView
from .views.stm_view import STMView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_NAV = [
    ("Dashboard",   "dashboard"),
    ("Short-Term",  "stm"),
    ("Mid-Term",    "mtm"),
    ("Long-Term",   "ltm"),
    ("Settings",    "settings"),
    ("Log",         "log"),
]

_CHECK_MS = 10_000


class PMSEditorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PMS Editor — Personal Memory System")
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.client = PMSClient()
        self._active: str | None = None
        self._nav_btns: dict[str, ctk.CTkButton] = {}

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
            bar, text="PMS Editor", font=("Arial", 15, "bold")
        ).grid(row=0, column=0, padx=(16, 24), pady=12)

        ctk.CTkLabel(bar, text="Server URL:", text_color="#aaa").grid(
            row=0, column=1, sticky="e", padx=(0, 4)
        )
        self._url_entry = ctk.CTkEntry(
            bar, width=260, placeholder_text="http://127.0.0.1:8765"
        )
        self._url_entry.insert(0, self.client.base_url)
        self._url_entry.grid(row=0, column=2, padx=(0, 8), pady=10)
        self._url_entry.bind("<Return>", lambda _: self._connect())

        self._btn_connect = ctk.CTkButton(
            bar, text="Connect", width=80, height=32, command=self._connect
        )
        self._btn_connect.grid(row=0, column=3, padx=(0, 12))

        self._status_lbl = ctk.CTkLabel(
            bar, text="●  Not connected", text_color="#888", font=("Arial", 12)
        )
        self._status_lbl.grid(row=0, column=4, padx=(0, 20))

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        for i, (label, key) in enumerate(_NAV):
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
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

        self._panels: dict[str, ctk.CTkFrame] = {
            "dashboard": DashboardView(container, self.client),
            "stm":       STMView(container, self.client),
            "mtm":       MTMView(container, self.client),
            "ltm":       LTMView(container, self.client),
            "settings":  SettingsView(container, self.client),
            "log":       LogView(container, self.client),
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

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        url = self._url_entry.get().strip().rstrip("/")
        if url:
            self.client = PMSClient(url if url.startswith("http") else "http://" + url)
            for panel in self._panels.values():
                panel.client = self.client

        self._btn_connect.configure(state="disabled", text="Connecting…")
        self._status_lbl.configure(text="●  Connecting…", text_color="#f0a500")
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self) -> None:
        alive = self.client.is_alive()
        if alive:
            self.after(0, lambda: (
                self._status_lbl.configure(
                    text=f"●  Connected  {self.client.base_url}",
                    text_color="#2ecc71",
                ),
                self._btn_connect.configure(state="normal", text="Connect"),
            ))
            self.after(0, lambda: self._panels[self._active].refresh() if self._active else None)
        else:
            self.after(0, lambda: (
                self._status_lbl.configure(
                    text="●  Cannot connect — is the API running?",
                    text_color="#e74c3c",
                ),
                self._btn_connect.configure(state="normal", text="Connect"),
            ))
        self.after(_CHECK_MS, self._connect_silent)

    def _connect_silent(self) -> None:
        """Periodic background health check (no UI changes on reconnect)."""
        def _check() -> None:
            alive = self.client.is_alive()
            color = "#2ecc71" if alive else "#e74c3c"
            text = (
                f"●  Connected  {self.client.base_url}" if alive
                else "●  Cannot connect — is the API running?"
            )
            self.after(0, lambda: self._status_lbl.configure(
                text=text, text_color=color
            ))
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
