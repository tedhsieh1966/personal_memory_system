"""LTM view — concepts with semantic search, delete, export."""
from __future__ import annotations

import json
import tkinter as tk
import tkinter.filedialog as fd
import customtkinter as ctk

from . import ViewBase, confirm_dialog, fmt_time


class LTMView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header + search ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(hdr, text="Long-Term Memory",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self._count_lbl = ctk.CTkLabel(hdr, text="", text_color="gray60")
        self._count_lbl.pack(side="left", padx=12)
        ctk.CTkButton(hdr, text="Refresh", width=80, command=self.refresh).pack(side="right")

        # ── Search bar ─────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_row, textvariable=self._search_var,
            placeholder_text="Semantic search…", width=320,
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<Return>", lambda _: self._do_search())
        ctk.CTkButton(search_row, text="Search", width=80,
                      command=self._do_search).pack(side="left", padx=8)

        # ── Column headers ─────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(self, fg_color="gray20")
        col_hdr.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 2))
        ctk.CTkLabel(col_hdr, text="ID",      width=90,  anchor="w").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(col_hdr, text="Concept", anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_hdr, text="Updated", width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(col_hdr, text="",        width=140).pack(side="right")

        # ── Scrollable list ────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.grid_rowconfigure(3, weight=1)

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="gray60")
        self._status_lbl.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 8))

    def refresh(self) -> None:
        self._search_var.set("")
        self._status_lbl.configure(text="Loading…")
        self._run_async(self.client.list_ltm, self._on_data)

    def _do_search(self) -> None:
        q = self._search_var.get().strip()
        if not q:
            self.refresh()
            return
        self._status_lbl.configure(text="Searching…")
        self._run_async(lambda: self.client.retrieve(q, top_k=20), self._on_search)

    def _on_search(self, data: dict | None, err: Exception | None) -> None:
        if err or not data:
            self._status_lbl.configure(text=f"Search error: {err}")
            return
        # retrieve returns {results: [...], partial: bool}; extract LTM hits
        results = data.get("results", [])
        ltm = [r for r in results if r.get("tier") == "ltm"]
        # reformat to match list_ltm shape
        converted = [
            {"id": r["id"], "concept": r["content"], "updated_at": r.get("timestamp"), "created_at": r.get("timestamp")}
            for r in ltm
        ]
        self._count_lbl.configure(text=f"({len(converted)} matches)")
        self._status_lbl.configure(text="partial results" if data.get("partial") else "")
        self._render_rows(converted)

    def _on_data(self, rows: list[dict] | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Error: {err}")
            return
        rows = rows or []
        self._count_lbl.configure(text=f"({len(rows)} concepts)")
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

            ctk.CTkLabel(row, text=short_id, width=90, anchor="w",
                         text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=concept, anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=updated, width=120, anchor="w",
                         text_color="gray60").pack(side="left")
            ctk.CTkButton(
                row, text="Export", width=62, fg_color="gray40",
                command=lambda i=cid, c=item.get("concept", ""): self._export(i, c),
            ).pack(side="right", padx=2, pady=2)
            ctk.CTkButton(
                row, text="Delete", width=62,
                fg_color="#8B2020", hover_color="#B22222",
                command=lambda i=cid: self._delete(i),
            ).pack(side="right", padx=2, pady=2)

            ctk.CTkFrame(self._scroll, height=1, fg_color="gray25").pack(fill="x")

    def _delete(self, concept_id: str) -> None:
        if not confirm_dialog("Delete Concept", f"Delete LTM concept {concept_id[:12]}…?"):
            return
        self._run_async(lambda: self.client.delete_ltm(concept_id), self._on_deleted)

    def _on_deleted(self, _: object, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Delete failed: {err}")
        self.refresh()

    def _export(self, concept_id: str, concept_text: str) -> None:
        path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt"), ("All", "*.*")],
            initialfile=f"concept_{concept_id[:8]}",
        )
        if not path:
            return
        payload = {"id": concept_id, "concept": concept_text}
        with open(path, "w", encoding="utf-8") as f:
            if path.endswith(".txt"):
                f.write(concept_text)
            else:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        self._status_lbl.configure(text=f"Exported to {path}")
