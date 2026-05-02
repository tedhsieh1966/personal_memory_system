"""STM view — scrollable list of raw events with delete."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm, fmt_time

_COL_TIME = 130
_COL_SRC  = 80
_COL_KW   = 160


class STMView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            hdr, text=self.tr("stm.title"), font=("Arial", 16, "bold")
        ).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="#aaa", font=("Arial", 12))
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(
            hdr, text=self.tr("common.refresh"), width=80, height=30, command=self.refresh
        ).pack(side="right")

        # ── Column headers ─────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=0)
        col_hdr.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text=self.tr("col.time"),     width=_COL_TIME, anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text=self.tr("col.source"),   width=_COL_SRC,  anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(col_hdr, text=self.tr("col.keywords"), width=_COL_KW,   anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(col_hdr, text=self.tr("col.content"),  anchor="w",                  font=("Arial", 12, "bold")).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text="", width=68).pack(side="right")

        # ── Scrollable list ────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="#aaa", font=("Arial", 12))
        self._status_lbl.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 12))

    def refresh(self) -> None:
        self._status_lbl.configure(text=self.tr("common.loading"))
        self._run_async(self.client.list_stm, self._on_data)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.error')}: {err}", text_color="#e74c3c"
            )
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} {self.tr('unit.events')})")
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

            ctk.CTkLabel(row, text=fmt_time(item.get("created_at")), width=_COL_TIME, anchor="w", font=("Arial", 12)).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=item.get("source", ""),           width=_COL_SRC,  anchor="w", font=("Arial", 12)).pack(side="left")
            ctk.CTkLabel(row, text=kw, width=_COL_KW, anchor="w", text_color="#aaa",  font=("Arial", 12)).pack(side="left")
            ctk.CTkLabel(row, text=content, anchor="w",              font=("Arial", 12)).pack(side="left", fill="x", expand=True)

            eid = item["id"]
            ctk.CTkButton(
                row, text=self.tr("common.delete"), width=62, height=26,
                fg_color="#c0392b", hover_color="#922b21", font=("Arial", 12),
                command=lambda i=eid: self._delete(i),
            ).pack(side="right", padx=4, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="#2a2d2e").pack(fill="x")

    def _delete(self, event_id: int) -> None:
        if not confirm(
            self.tr("confirm.delete_stm_title"),
            f"{self.tr('confirm.delete_stm_msg')} #{event_id}?",
        ):
            return
        self._run_async(lambda: self.client.delete_stm(event_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.delete_failed')}: {err}", text_color="#e74c3c"
            )
        self.refresh()
