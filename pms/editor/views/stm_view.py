"""STM view — scrollable list of raw events with delete."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm_dialog, fmt_time

_COL_TIME = 130
_COL_SRC  = 80
_COL_KW   = 160


class STMView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header bar ─────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(hdr, text="Short-Term Memory",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="gray60")
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(hdr, text="Refresh", width=80, command=self.refresh).pack(side="right")

        # ── Column headers ─────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="gray20")
        col_hdr.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text="Time",    width=_COL_TIME, anchor="w").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text="Source",  width=_COL_SRC,  anchor="w").pack(side="left")
        ctk.CTkLabel(col_hdr, text="Keywords",width=_COL_KW,   anchor="w").pack(side="left")
        ctk.CTkLabel(col_hdr, text="Content", anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text="", width=68).pack(side="right")

        # ── Scrollable list ────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.grid_rowconfigure(2, weight=1)

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="gray60")
        self._status_lbl.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))

    def refresh(self) -> None:
        self._status_lbl.configure(text="Loading…")
        self._run_async(self.client.list_stm, self._on_data)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Error: {err}")
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} events)")
        self._status_lbl.configure(text="")
        self._render_rows(rows)

    def _render_rows(self, data: list[dict]) -> None:
        for w in self._rows:
            w.destroy()
        self._rows.clear()

        for item in data:
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            self._rows.append(row)

            kw = ", ".join(item.get("keywords") or [])[:40]
            content = (item.get("content") or "")[:120]

            ctk.CTkLabel(row, text=fmt_time(item.get("created_at")),
                         width=_COL_TIME, anchor="w").pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=item.get("source", ""),
                         width=_COL_SRC, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=kw, width=_COL_KW, anchor="w",
                         text_color="gray70").pack(side="left")
            ctk.CTkLabel(row, text=content, anchor="w",
                         text_color="gray90").pack(side="left", fill="x", expand=True)

            eid = item["id"]
            ctk.CTkButton(
                row, text="Delete", width=62,
                fg_color="#8B2020", hover_color="#B22222",
                command=lambda i=eid: self._delete(i),
            ).pack(side="right", padx=4, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="gray25").pack(fill="x")

    def _delete(self, event_id: int) -> None:
        if not confirm_dialog("Delete STM Event", f"Delete STM event #{event_id}?"):
            return
        self._run_async(lambda: self.client.delete_stm(event_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Delete failed: {err}")
        self.refresh()
