"""PMS Editor — main CustomTkinter application window."""
from __future__ import annotations

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
    ("Dashboard", "dashboard"),
    ("Short-Term",  "stm"),
    ("Mid-Term",    "mtm"),
    ("Long-Term",   "ltm"),
    ("Settings",    "settings"),
    ("Log",         "log"),
]

_CHECK_MS = 5_000   # connection check interval


class PMSEditorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Personal Memory System")
        self.geometry("1280x740")
        self.minsize(900, 600)

        self.client = PMSClient()
        self._views: dict[str, ctk.CTkFrame] = {}
        self._active: str = ""
        self._nav_btns: dict[str, ctk.CTkButton] = {}

        self._build_layout()
        self._build_sidebar()
        self._build_views()
        self._build_statusbar()

        self._show_view("dashboard")
        self._check_connection()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._sidebar = ctk.CTkFrame(self, width=180, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)

        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        self._statusbar = ctk.CTkFrame(self, height=28, corner_radius=0,
                                       fg_color="gray15")
        self._statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _build_sidebar(self) -> None:
        ctk.CTkLabel(
            self._sidebar, text="PMS",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(20, 4))
        ctk.CTkLabel(
            self._sidebar, text="Personal Memory",
            font=ctk.CTkFont(size=11), text_color="gray60",
        ).pack(pady=(0, 20))

        for label, key in _NAV:
            btn = ctk.CTkButton(
                self._sidebar, text=label,
                corner_radius=6, anchor="w",
                fg_color="transparent", hover_color="gray25",
                command=lambda k=key: self._show_view(k),
            )
            btn.pack(fill="x", padx=10, pady=3)
            self._nav_btns[key] = btn

        # Connection section at bottom
        self._sidebar.pack_propagate(False)
        spacer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        ctk.CTkFrame(self._sidebar, height=1, fg_color="gray35").pack(fill="x", padx=10)
        self._host_entry = ctk.CTkEntry(
            self._sidebar, placeholder_text="127.0.0.1:8765", width=160
        )
        self._host_entry.insert(0, "127.0.0.1:8765")
        self._host_entry.pack(padx=10, pady=(8, 4))
        ctk.CTkButton(
            self._sidebar, text="Connect", width=160,
            command=self._reconnect,
        ).pack(padx=10, pady=(0, 16))

    def _build_views(self) -> None:
        self._views = {
            "dashboard": DashboardView(self._content, self.client),
            "stm":       STMView(self._content, self.client),
            "mtm":       MTMView(self._content, self.client),
            "ltm":       LTMView(self._content, self.client),
            "settings":  SettingsView(self._content, self.client),
            "log":       LogView(self._content, self.client),
        }
        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

    def _build_statusbar(self) -> None:
        self._status_lbl = ctk.CTkLabel(
            self._statusbar, text="", font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self._status_lbl.pack(side="left", padx=12)

        self._conn_lbl = ctk.CTkLabel(
            self._statusbar, text="● Checking…",
            font=ctk.CTkFont(size=11), text_color="gray50",
        )
        self._conn_lbl.pack(side="right", padx=12)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_view(self, key: str) -> None:
        if key not in self._views:
            return
        if self._active and self._active in self._nav_btns:
            self._nav_btns[self._active].configure(fg_color="transparent")
        self._active = key
        self._nav_btns[key].configure(fg_color="gray25")
        self._views[key].tkraise()
        self._views[key].refresh()

    # ── Connection ────────────────────────────────────────────────────────────

    def _reconnect(self) -> None:
        addr = self._host_entry.get().strip() or "127.0.0.1:8765"
        if not addr.startswith("http"):
            addr = "http://" + addr
        self.client.close()
        self.client = PMSClient(addr)
        for view in self._views.values():
            view.client = self.client
        self._check_connection()

    def _check_connection(self) -> None:
        import threading

        def _ping() -> bool:
            return self.client.is_alive()

        def _on_result(alive: bool) -> None:
            if alive:
                self._conn_lbl.configure(
                    text=f"● Connected  {self.client.base_url}",
                    text_color="#4CAF50",
                )
                self._hide_banner()
            else:
                self._conn_lbl.configure(
                    text="● API not reachable", text_color="#FF6B6B"
                )
                self._show_banner()

        def _target() -> None:
            result = _ping()
            self.after(0, lambda: _on_result(result))

        threading.Thread(target=_target, daemon=True).start()
        self.after(_CHECK_MS, self._check_connection)

    def _show_banner(self) -> None:
        if hasattr(self, "_banner") and self._banner.winfo_exists():
            return
        self._banner = ctk.CTkFrame(self._content, fg_color="#5C2020", corner_radius=0)
        self._banner.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(
            self._banner,
            text="PMS API is not reachable. Check that the service is running, then click Connect.",
            text_color="#FFAAAA",
        ).pack(pady=6)
        self._content.grid_rowconfigure(1, minsize=36)

    def _hide_banner(self) -> None:
        if hasattr(self, "_banner") and self._banner.winfo_exists():
            self._banner.destroy()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_close(self) -> None:
        self.client.close()
        self.destroy()


def run() -> None:
    app = PMSEditorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
