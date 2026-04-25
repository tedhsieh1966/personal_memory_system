from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..models import MTMPatch
from ..services import ltm as ltm_svc
from ..services import mtm as mtm_svc
from ..services import stm as stm_svc

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/stm")
async def list_stm(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return await asyncio.to_thread(stm_svc.list_events, limit, offset)


@router.get("/mtm")
async def list_mtm(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    min_score: float | None = Query(default=None, ge=0),
) -> list[dict]:
    return await asyncio.to_thread(mtm_svc.list_episodes, limit, offset, min_score)


@router.get("/ltm")
async def list_ltm(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return await asyncio.to_thread(ltm_svc.list_concepts, limit, offset)


@router.delete("/stm/{event_id}", status_code=204)
async def delete_stm(event_id: int) -> None:
    deleted = await asyncio.to_thread(stm_svc.delete_event, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="STM event not found")


@router.delete("/mtm/{ep_id}", status_code=204)
async def delete_mtm(ep_id: int) -> None:
    deleted = await asyncio.to_thread(mtm_svc.delete_episode, ep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MTM episode not found")


@router.patch("/mtm/{ep_id}")
async def patch_mtm(ep_id: int, body: MTMPatch) -> dict:
    updated = await asyncio.to_thread(
        mtm_svc.patch_episode, ep_id, body.pinned, body.importance_score
    )
    if not updated:
        raise HTTPException(status_code=404, detail="MTM episode not found")
    return {"id": ep_id, "updated": True}


@router.delete("/ltm/{concept_id}", status_code=204)
async def delete_ltm(concept_id: str) -> None:
    raise HTTPException(status_code=501, detail="LTM not available until Phase 2")
