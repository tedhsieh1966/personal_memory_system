"""LTM view — concepts with semantic search, delete, export."""
from __future__ import annotations

import json
import tkinter.filedialog as fd
import customtkinter as ctk

from . import ViewBase, confirm, fmt_time


class LTMView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(hdr, text=self.tr("ltm.title"), font=("Arial", 16, "bold")).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="#aaa", font=("Arial", 12))
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(
            hdr, text=self.tr("common.refresh"), width=80, height=30, command=self.refresh
        ).pack(side="right")

        # ── Search bar ─────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        self._search_entry = ctk.CTkEntry(
            search_row, placeholder_text=self.tr("ltm.search_placeholder"),
            width=340, height=34, font=("Arial", 13),
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<Return>", lambda _: self._do_search())
        ctk.CTkButton(
            search_row, text=self.tr("common.search"), width=80, height=34,
            command=self._do_search,
        ).pack(side="left", padx=8)

        # ── Column headers ─────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=0)
        col_hdr.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text=self.tr("col.id"),      width=90,  anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text=self.tr("col.concept"), anchor="w",             font=("Arial", 12, "bold")).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text=self.tr("col.updated"), width=120, anchor="w",  font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(col_hdr, text="", width=140).pack(side="right")

        # ── Scrollable list ────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 8))

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="#aaa", font=("Arial", 12))
        self._status_lbl.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 12))

    def refresh(self) -> None:
        self._search_entry.delete(0, "end")
        self._status_lbl.configure(text=self.tr("common.loading"), text_color="#aaa")
        self._run_async(self.client.list_ltm, self._on_data)

    def _do_search(self) -> None:
        q = self._search_entry.get().strip()
        if not q:
            self.refresh()
            return
        self._status_lbl.configure(text=self.tr("ltm.searching"), text_color="#f0a500")
        self._run_async(lambda: self.client.retrieve(q, top_k=20), self._on_search)

    def _on_search(self, data: dict | None, err: Exception | None) -> None:
        if err or not data:
            self._status_lbl.configure(
                text=f"{self.tr('ltm.search_error')}: {err}", text_color="#e74c3c"
            )
            return
        results = data.get("results", [])
        ltm = [r for r in results if r.get("tier") == "ltm"]
        converted = [
            {"id": r["id"], "concept": r["content"],
             "updated_at": r.get("timestamp"), "created_at": r.get("timestamp")}
            for r in ltm
        ]
        self._count_lbl.configure(text=f"({len(converted)} {self.tr('unit.matches')})")
        partial_note = self.tr("ltm.partial_note") if data.get("partial") else ""
        self._status_lbl.configure(text=partial_note, text_color="#aaa")
        self._render_rows(converted)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.error')}: {err}", text_color="#e74c3c"
            )
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} {self.tr('unit.concepts')})")
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

            short_id = str(item.get("id", ""))[:12]
            concept = (item.get("concept") or "")[:160]
            updated = fmt_time(item.get("updated_at") or item.get("created_at"))
            cid = item["id"]

            ctk.CTkLabel(row, text=short_id, width=90, anchor="w", text_color="#aaa", font=("Arial", 11)).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=concept, anchor="w", font=("Arial", 12)).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=updated, width=120, anchor="w", text_color="#aaa", font=("Arial", 12)).pack(side="left")

            ctk.CTkButton(
                row, text=self.tr("common.export"), width=62, height=26,
                fg_color="#2a2d2e", hover_color="#3a3d3e", font=("Arial", 12),
                command=lambda i=cid, c=item.get("concept", ""): self._export(i, c),
            ).pack(side="right", padx=2, pady=2)
            ctk.CTkButton(
                row, text=self.tr("common.delete"), width=62, height=26,
                fg_color="#c0392b", hover_color="#922b21", font=("Arial", 12),
                command=lambda i=cid: self._delete(i),
            ).pack(side="right", padx=2, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="#2a2d2e").pack(fill="x")

    def _delete(self, concept_id: str) -> None:
        if not confirm(
            self.tr("confirm.delete_concept_title"),
            f"{self.tr('confirm.delete_concept_msg')} {concept_id[:12]}…?",
        ):
            return
        self._run_async(lambda: self.client.delete_ltm(concept_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(
                text=f"{self.tr('common.delete_failed')}: {err}", text_color="#e74c3c"
            )
        self.refresh()

    def _export(self, concept_id: str, concept_text: str) -> None:
        path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt"), ("All", "*.*")],
            initialfile=f"concept_{concept_id[:8]}",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            if path.endswith(".txt"):
                f.write(concept_text)
            else:
                json.dump({"id": concept_id, "concept": concept_text}, f,
                          indent=2, ensure_ascii=False)
        self._status_lbl.configure(
            text=f"{self.tr('ltm.exported')} {path}", text_color="#2ecc71"
        )
