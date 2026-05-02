"""MTM view — episodes with score progress bar, pin/unpin, delete."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm, fmt_time

_COL_TIME  = 120
_COL_SCORE = 140
_COL_TAGS  = 160


class MTMView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(hdr, text=self.tr("mtm.title"), font=("Arial", 16, "bold")).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="#aaa", font=("Arial", 12))
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(
            hdr, text=self.tr("common.refresh"), width=80, height=30, command=self.refresh
        ).pack(side="right")

        col_hdr = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=0)
        col_hdr.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text=self.tr("col.time"),    width=_COL_TIME,  anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text=self.tr("col.score"),   width=_COL_SCORE, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(col_hdr, text=self.tr("col.tags"),    width=_COL_TAGS,  anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(col_hdr, text=self.tr("col.summary"), anchor="w",                   font=("Arial", 12, "bold")).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text="", width=140).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="#aaa", font=("Arial", 12))
        self._status_lbl.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 12))

    def refresh(self) -> None:
        self._status_lbl.configure(text=self.tr("common.loading"))
        self._run_async(self.client.list_mtm, self._on_data)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.error')}: {err}", text_color="#e74c3c"
            )
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} {self.tr('unit.episodes')})")
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

            score = float(item.get("importance_score", 0.0))
            tags = ", ".join(item.get("topic_tags") or [])[:40]
            summary = (item.get("summary") or "")[:140]
            pinned = bool(item.get("pinned"))
            eid = item["id"]

            ctk.CTkLabel(row, text=fmt_time(item.get("created_at")), width=_COL_TIME, anchor="w", font=("Arial", 12)).pack(side="left", padx=(4, 0))

            score_frame = ctk.CTkFrame(row, fg_color="transparent", width=_COL_SCORE)
            score_frame.pack(side="left")
            score_frame.pack_propagate(False)
            bar = ctk.CTkProgressBar(score_frame, width=80, height=10)
            bar.pack(side="left", pady=10)
            bar.set(min(1.0, score / 10.0))
            ctk.CTkLabel(score_frame, text=f"{score:.1f}", width=40, font=("Arial", 12)).pack(side="left")

            ctk.CTkLabel(row, text=tags, width=_COL_TAGS, anchor="w", text_color="#aaa", font=("Arial", 12)).pack(side="left")
            ctk.CTkLabel(row, text=summary, anchor="w", font=("Arial", 12)).pack(side="left", fill="x", expand=True)

            pin_color = "#1a7a3c" if pinned else "#2a2d2e"
            pin_text = self.tr("common.unpin") if pinned else self.tr("common.pin")
            ctk.CTkButton(
                row, text=pin_text, width=58, height=26,
                fg_color=pin_color, font=("Arial", 12),
                command=lambda i=eid, p=pinned: self._toggle_pin(i, p),
            ).pack(side="right", padx=2, pady=2)
            ctk.CTkButton(
                row, text=self.tr("common.delete"), width=62, height=26,
                fg_color="#c0392b", hover_color="#922b21", font=("Arial", 12),
                command=lambda i=eid: self._delete(i),
            ).pack(side="right", padx=2, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="#2a2d2e").pack(fill="x")

    def _toggle_pin(self, ep_id: int, currently_pinned: bool) -> None:
        if currently_pinned:
            title = self.tr("confirm.unpin_title")
            msg   = f"{self.tr('confirm.unpin_msg')} #{ep_id}?"
        else:
            title = self.tr("confirm.pin_title")
            msg   = f"{self.tr('confirm.pin_msg')} #{ep_id}?"
        if not confirm(title, msg):
            return
        self._run_async(
            lambda: self.client.patch_mtm(ep_id, pinned=not currently_pinned),
            lambda _, e: self.refresh(),
        )

    def _delete(self, ep_id: int) -> None:
        if not confirm(
            self.tr("confirm.delete_episode_title"),
            f"{self.tr('confirm.delete_episode_msg')} #{ep_id}?",
        ):
            return
        self._run_async(lambda: self.client.delete_mtm(ep_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.delete_failed')}: {err}", text_color="#e74c3c"
            )
        self.refresh()
