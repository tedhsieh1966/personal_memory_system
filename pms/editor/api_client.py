"""Synchronous httpx client wrapping all PMS REST endpoints."""
from __future__ import annotations

from typing import Any

import httpx


class PMSClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def close(self) -> None:
        self._client.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get(self, path: str, **params: Any) -> Any:
        r = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict | None = None) -> Any:
        r = self._client.post(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, json: dict) -> bool:
        r = self._client.patch(path, json=json)
        return r.status_code == 200

    def _delete(self, path: str) -> bool:
        r = self._client.delete(path)
        return r.status_code in (200, 204)

    # ── connection ────────────────────────────────────────────────────────────

    def is_alive(self) -> bool:
        try:
            self._client.get("/status", timeout=2.0).raise_for_status()
            return True
        except Exception:
            return False

    def get_status(self) -> dict:
        return self._get("/status")

    # ── ingest / retrieve ─────────────────────────────────────────────────────

    def ingest(self, content: str, source: str = "manual", metadata: dict | None = None) -> dict:
        return self._post("/ingest", json={
            "source": source,
            "content": content,
            "metadata": metadata or {},
        })

    def retrieve(self, q: str, top_k: int = 10) -> dict:
        return self._get("/retrieve", q=q, top_k=top_k)

    # ── STM ───────────────────────────────────────────────────────────────────

    def list_stm(self, limit: int = 200, offset: int = 0) -> list[dict]:
        return self._get("/memory/stm", limit=limit, offset=offset)

    def delete_stm(self, event_id: int) -> bool:
        return self._delete(f"/memory/stm/{event_id}")

    # ── MTM ───────────────────────────────────────────────────────────────────

    def list_mtm(self, limit: int = 200, offset: int = 0, min_score: float | None = None) -> list[dict]:
        return self._get("/memory/mtm", limit=limit, offset=offset, min_score=min_score)

    def patch_mtm(self, ep_id: int, pinned: bool | None = None, importance_score: float | None = None) -> bool:
        payload: dict = {}
        if pinned is not None:
            payload["pinned"] = pinned
        if importance_score is not None:
            payload["importance_score"] = importance_score
        return self._patch(f"/memory/mtm/{ep_id}", json=payload)

    def delete_mtm(self, ep_id: int) -> bool:
        return self._delete(f"/memory/mtm/{ep_id}")

    # ── LTM ───────────────────────────────────────────────────────────────────

    def list_ltm(self, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._get("/memory/ltm", limit=limit, offset=offset)

    def delete_ltm(self, concept_id: str) -> bool:
        return self._delete(f"/memory/ltm/{concept_id}")

    # ── admin ─────────────────────────────────────────────────────────────────

    def consolidate_stm(self) -> dict:
        return self._post("/consolidate/stm")

    def consolidate_mtm(self) -> dict:
        return self._post("/consolidate/mtm")

    def get_config(self) -> dict:
        return self._get("/config")

    def update_config(self, updates: dict) -> dict:
        return self._post("/config", json={"config": updates})
