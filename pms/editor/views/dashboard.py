"""Dashboard view — counts, scheduler status, quick actions."""
from __future__ import annotations

import customtkinter as ctk

from . import ViewBase, confirm_dialog


class DashboardView(ViewBase):
    def __init__(self, parent, client, **kwargs):
        super().__init__(parent, client, **kwargs)
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Title ──────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Dashboard", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 10)
        )

        # ── Count cards ────────────────────────────────────────────────────
        card_row = ctk.CTkFrame(self, fg_color="transparent")
        card_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 12))
        card_row.grid_columnconfigure((0, 1, 2), weight=1)

        self._stm_lbl = self._make_card(card_row, "STM Events", 0)
        self._mtm_lbl = self._make_card(card_row, "MTM Episodes", 1)
        self._ltm_lbl = self._make_card(card_row, "LTM Concepts", 2)

        # ── Left column: scheduler + quick actions ──────────────────────────
        left = ctk.CTkFrame(self)
        left.grid(row=2, column=0, sticky="nsew", padx=(20, 8), pady=0)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Scheduler", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=14, pady=(14, 6)
        )
        self._sched_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._sched_frame.pack(fill="x", padx=14)

        self._sched_rows: dict[str, ctk.CTkLabel] = {}
        for task in ("STM→MTM", "MTM→LTM", "Maintenance"):
            row = ctk.CTkFrame(self._sched_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=task, width=100, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", anchor="w", text_color="gray60")
            lbl.pack(side="left")
            self._sched_rows[task] = lbl

        ctk.CTkFrame(left, height=1, fg_color="gray30").pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(left, text="Quick Actions", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=14, pady=(0, 8)
        )
        self._status_lbl = ctk.CTkLabel(left, text="", text_color="gray60", wraplength=280)
        self._status_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        ctk.CTkButton(left, text="Consolidate STM → MTM", command=self._consolidate_stm).pack(
            fill="x", padx=14, pady=3
        )
        ctk.CTkButton(left, text="Consolidate MTM → LTM", command=self._consolidate_mtm).pack(
            fill="x", padx=14, pady=3
        )

        # ── Right column: add memory ────────────────────────────────────────
        right = ctk.CTkFrame(self)
        right.grid(row=2, column=1, sticky="nsew", padx=(8, 20), pady=0)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Add Memory", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=14, pady=(14, 6)
        )
        self._ingest_box = ctk.CTkTextbox(right, height=180)
        self._ingest_box.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        ctk.CTkButton(right, text="Add Memory", command=self._add_memory).pack(
            fill="x", padx=14, pady=(0, 14)
        )

    def _make_card(self, parent: ctk.CTkFrame, label: str, col: int) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=col, sticky="ew", padx=6, pady=4)
        ctk.CTkLabel(card, text=label, text_color="gray60", font=ctk.CTkFont(size=12)).pack(
            pady=(10, 2)
        )
        count_lbl = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=28, weight="bold"))
        count_lbl.pack(pady=(0, 10))
        return count_lbl

    def refresh(self) -> None:
        self._run_async(self.client.get_status, self._on_status)

    def _on_status(self, data: dict | None, err: Exception | None) -> None:
        if err or not data:
            return
        self._stm_lbl.configure(text=str(data.get("stm_count", "—")))
        self._mtm_lbl.configure(text=str(data.get("mtm_count", "—")))
        self._ltm_lbl.configure(text=str(data.get("ltm_count", "—")))

        from . import fmt_time
        self._sched_rows["STM→MTM"].configure(
            text=fmt_time(data.get("last_stm_consolidation"))
        )
        self._sched_rows["MTM→LTM"].configure(
            text=fmt_time(data.get("last_mtm_consolidation"))
        )
        self._sched_rows["Maintenance"].configure(
            text=fmt_time(data.get("last_maintenance"))
        )
        running = data.get("scheduler_running", False)
        status_txt = "Scheduler: running" if running else "Scheduler: stopped"
        self._status_lbl.configure(text=status_txt)

    def _consolidate_stm(self) -> None:
        if not confirm_dialog("Consolidate STM", "Run STM → MTM consolidation now?"):
            return
        self._status_lbl.configure(text="Running STM → MTM…")
        self._run_async(self.client.consolidate_stm, self._on_consolidate)

    def _consolidate_mtm(self) -> None:
        if not confirm_dialog("Consolidate MTM", "Run MTM → LTM consolidation now?"):
            return
        self._status_lbl.configure(text="Running MTM → LTM…")
        self._run_async(self.client.consolidate_mtm, self._on_consolidate)

    def _on_consolidate(self, data: dict | None, err: Exception | None) -> None:
        if err:
            self._status_lbl.configure(text=f"Error: {err}")
        else:
            self._status_lbl.configure(text=f"Done: {data}")
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
            self._status_lbl.configure(text=f"Ingest error: {err}")
        else:
            self._ingest_box.delete("1.0", "end")
            self._status_lbl.configure(text="Memory added.")
            self.refresh()
