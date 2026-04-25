"""Dashboard view — counts, scheduler status, quick actions, add memory."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm, fmt_time


class DashboardView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text="Dashboard", font=("Arial", 16, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 12))

        # ── Count cards ────────────────────────────────────────────────────
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 12))
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        self._stm_lbl = self._make_card(cards, "STM Events",   0)
        self._mtm_lbl = self._make_card(cards, "MTM Episodes", 1)
        self._ltm_lbl = self._make_card(cards, "LTM Concepts", 2)

        # ── Left: scheduler + actions ──────────────────────────────────────
        left = ctk.CTkFrame(self)
        left.grid(row=2, column=0, sticky="nsew", padx=(20, 8), pady=(0, 20))
        left.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            left, text="Scheduler", font=("Arial", 13, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

        self._add_info_row(left, 1, "STM→MTM last run",  "lbl_last_stm")
        self._add_info_row(left, 2, "MTM→LTM last run",  "lbl_last_mtm")
        self._add_info_row(left, 3, "Maintenance last run", "lbl_last_maint", pad_bottom=12)

        ctk.CTkFrame(left, height=1, fg_color="gray30").grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=0
        )

        ctk.CTkLabel(
            left, text="Quick Actions", font=("Arial", 13, "bold")
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

        self._action_lbl = ctk.CTkLabel(
            left, text="", text_color="#aaa", font=("Arial", 12), anchor="w"
        )
        self._action_lbl.grid(row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))

        ctk.CTkButton(
            left, text="Consolidate STM → MTM", height=34,
            command=self._consolidate_stm,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", padx=12, pady=3)

        ctk.CTkButton(
            left, text="Consolidate MTM → LTM", height=34,
            command=self._consolidate_mtm,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", padx=12, pady=(3, 14))

        # ── Right: add memory ──────────────────────────────────────────────
        right = ctk.CTkFrame(self)
        right.grid(row=2, column=1, sticky="nsew", padx=(8, 20), pady=(0, 20))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right, text="Add Memory", font=("Arial", 13, "bold")
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self._ingest_box = ctk.CTkTextbox(right, font=("Arial", 13))
        self._ingest_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        ctk.CTkButton(
            right, text="Add Memory", height=34,
            fg_color="#1a7a3c", hover_color="#145e2e",
            command=self._add_memory,
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 14))

    def _make_card(self, parent: ctk.CTkFrame, label: str, col: int) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=col, sticky="ew", padx=6, pady=4)
        ctk.CTkLabel(card, text=label, text_color="#aaa", font=("Arial", 12)).pack(pady=(10, 2))
        count = ctk.CTkLabel(card, text="—", font=("Arial", 28, "bold"))
        count.pack(pady=(0, 10))
        return count

    def refresh(self) -> None:
        self._run_async(self.client.get_status, self._on_status)

    def _on_status(self, data: dict | None, err: Exception | None) -> None:
        if err or not data:
            return
        self._stm_lbl.configure(text=str(data.get("stm_count", "—")))
        self._mtm_lbl.configure(text=str(data.get("mtm_count", "—")))
        self._ltm_lbl.configure(text=str(data.get("ltm_count", "—")))
        self.lbl_last_stm.configure(text=fmt_time(data.get("last_stm_consolidation")))
        self.lbl_last_mtm.configure(text=fmt_time(data.get("last_mtm_consolidation")))
        self.lbl_last_maint.configure(text=fmt_time(data.get("last_maintenance")))

    def _consolidate_stm(self) -> None:
        if not confirm("Consolidate STM", "Run STM → MTM consolidation now?"):
            return
        self._action_lbl.configure(text="Running STM → MTM…", text_color="#f0a500")
        self._run_async(self.client.consolidate_stm, self._on_consolidate)

    def _consolidate_mtm(self) -> None:
        if not confirm("Consolidate MTM", "Run MTM → LTM consolidation now?"):
            return
        self._action_lbl.configure(text="Running MTM → LTM…", text_color="#f0a500")
        self._run_async(self.client.consolidate_mtm, self._on_consolidate)

    def _on_consolidate(self, data: dict | None, err: Exception | None) -> None:
        if err:
            self._action_lbl.configure(text=f"Error: {err}", text_color="#e74c3c")
        else:
            self._action_lbl.configure(text=f"Done: {data}", text_color="#2ecc71")
        self.refresh()

    def _add_memory(self) -> None:
        text = self._ingest_box.get("1.0", "end").strip()
        if not text:
            return
        self._run_async(
            lambda: self.client.ingest(text, source="manual"),
            self._on_ingested,
        )

    def _on_ingested(self, data: dict | None, err: Exception | None) -> None:
        if err:
            self._action_lbl.configure(text=f"Ingest error: {err}", text_color="#e74c3c")
        else:
            self._ingest_box.delete("1.0", "end")
            self._action_lbl.configure(text="Memory added.", text_color="#2ecc71")
            self.refresh()
