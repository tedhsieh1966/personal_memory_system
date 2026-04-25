"""MTM view — episodes with score, pin/unpin, delete."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm_dialog, fmt_time

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

        # ── Header ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(hdr, text="Mid-Term Memory",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="gray60")
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(hdr, text="Refresh", width=80, command=self.refresh).pack(side="right")

        # ── Column headers ─────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="gray20")
        col_hdr.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text="Time",  width=_COL_TIME,  anchor="w").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text="Score", width=_COL_SCORE, anchor="w").pack(side="left")
        ctk.CTkLabel(col_hdr, text="Tags",  width=_COL_TAGS,  anchor="w").pack(side="left")
        ctk.CTkLabel(col_hdr, text="Summary", anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text="", width=140).pack(side="right")

        # ── Scrollable list ────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="gray60")
        self._status_lbl.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))

    def refresh(self) -> None:
        self._status_lbl.configure(text="Loading…")
        self._run_async(self.client.list_mtm, self._on_data)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Error: {err}")
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} episodes)")
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

            ctk.CTkLabel(row, text=fmt_time(item.get("created_at")),
                         width=_COL_TIME, anchor="w").pack(side="left", padx=(4, 0))

            # Score: progress bar + number
            score_frame = ctk.CTkFrame(row, fg_color="transparent", width=_COL_SCORE)
            score_frame.pack(side="left")
            score_frame.pack_propagate(False)
            ctk.CTkProgressBar(score_frame, width=80, height=10).pack(
                side="left", pady=10
            )
            bar = score_frame.winfo_children()[0]
            bar.set(min(1.0, score / 10.0))
            ctk.CTkLabel(score_frame, text=f"{score:.1f}", width=40).pack(side="left")

            ctk.CTkLabel(row, text=tags, width=_COL_TAGS, anchor="w",
                         text_color="gray70").pack(side="left")
            ctk.CTkLabel(row, text=summary, anchor="w",
                         text_color="gray90").pack(side="left", fill="x", expand=True)

            pin_text = "Unpin" if pinned else "Pin"
            pin_color = "#2D6A2D" if pinned else "gray40"
            ctk.CTkButton(
                row, text=pin_text, width=58, fg_color=pin_color,
                command=lambda i=eid, p=pinned: self._toggle_pin(i, p),
            ).pack(side="right", padx=2, pady=2)
            ctk.CTkButton(
                row, text="Delete", width=62,
                fg_color="#8B2020", hover_color="#B22222",
                command=lambda i=eid: self._delete(i),
            ).pack(side="right", padx=2, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="gray25").pack(fill="x")

    def _toggle_pin(self, ep_id: int, currently_pinned: bool) -> None:
        new_state = not currently_pinned
        verb = "Unpin" if currently_pinned else "Pin"
        if not confirm_dialog(f"{verb} Episode", f"{verb} episode #{ep_id}?"):
            return
        self._run_async(
            lambda: self.client.patch_mtm(ep_id, pinned=new_state),
            lambda _, e: self.refresh(),
        )

    def _delete(self, ep_id: int) -> None:
        if not confirm_dialog("Delete Episode", f"Delete MTM episode #{ep_id}?"):
            return
        self._run_async(lambda: self.client.delete_mtm(ep_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Delete failed: {err}")
        self.refresh()
