from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class IngestRequest(BaseModel):
    source: Literal["ai_chat", "browser", "file", "manual"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] | None = None


class RankedMemory(BaseModel):
    tier: Literal["stm", "mtm", "ltm"]
    id: int | str
    content: str
    score: float
    source: str
    timestamp: datetime


class RetrieveResponse(BaseModel):
    results: list[RankedMemory]
    partial: bool = False


class STMEvent(BaseModel):
    id: int
    source: str
    content: str
    keywords: list[str] | None
    metadata: dict[str, Any] | None
    created_at: datetime
    expires_at: datetime


class MTMEpisode(BaseModel):
    id: int
    summary: str
    topic_tags: list[str] | None
    importance_score: float
    access_count: int
    pinned: bool
    source_ids: list[int] | None
    created_at: datetime
    last_accessed: datetime | None
    expires_at: datetime | None


class LTMConcept(BaseModel):
    id: str
    concept: str
    source_ep_ids: list[str] | None
    created_at: datetime
    updated_at: datetime


class MTMPatch(BaseModel):
    pinned: bool | None = None
    importance_score: float | None = None


class ConfigUpdate(BaseModel):
    config: dict[str, Any]


class StatusResponse(BaseModel):
    stm_count: int
    mtm_count: int
    ltm_count: int
    scheduler_running: bool
    last_stm_consolidation: datetime | None
    last_mtm_consolidation: datetime | None
    last_maintenance: datetime | None
