from __future__ import annotations

import asyncio
from datetime import timezone

from fastapi import APIRouter

from ..config import get_config
from ..models import IngestRequest
from ..services import stm as stm_svc

router = APIRouter(prefix="/ingest", tags=["ingest"])

_consolidation_task: asyncio.Task | None = None


@router.post("", status_code=201)
async def ingest(req: IngestRequest) -> dict:
    ts = req.timestamp
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    event_id = await asyncio.to_thread(
        stm_svc.insert,
        req.source,
        req.content,
        ts,
        req.metadata,
    )

    asyncio.create_task(_maybe_consolidate())

    return {"id": event_id, "tier": "stm"}


async def _maybe_consolidate() -> None:
    """Fire STM→MTM consolidation in the background if capacity threshold is reached."""
    global _consolidation_task
    if _consolidation_task is not None and not _consolidation_task.done():
        return

    cfg = get_config()
    capacity: int = cfg["memory"]["stm_capacity"]
    pct: float = cfg["consolidation"]["stm_trigger_pct"]
    current = await asyncio.to_thread(stm_svc.count)

    if current >= capacity * pct:
        from ..services import consolidator, scheduler
        _consolidation_task = asyncio.create_task(
            asyncio.to_thread(scheduler.run_and_log, "stm_to_mtm", consolidator.run_stm_to_mtm)
        )
