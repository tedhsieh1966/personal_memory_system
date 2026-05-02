from __future__ import annotations

import asyncio
import copy

import yaml
from fastapi import APIRouter

from pms.service.config import get_config, get_config_path, load_config
from pms.service import consolidator
from pms.service import ltm as ltm_svc
from pms.service import mtm as mtm_svc
from pms.service import scheduler as sched_svc
from pms.service import stm as stm_svc

from ..models import ConfigUpdate, StatusResponse

router = APIRouter(tags=["admin"])


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    stm_count, mtm_count, ltm_count = await asyncio.gather(
        asyncio.to_thread(stm_svc.count),
        asyncio.to_thread(mtm_svc.count),
        asyncio.to_thread(ltm_svc.count),
    )
    last_stm, last_mtm, last_maint = await asyncio.gather(
        asyncio.to_thread(sched_svc.get_last_run, "stm_to_mtm"),
        asyncio.to_thread(sched_svc.get_last_run, "mtm_to_ltm"),
        asyncio.to_thread(sched_svc.get_last_run, "maintenance"),
    )
    return StatusResponse(
        stm_count=stm_count,
        mtm_count=mtm_count,
        ltm_count=ltm_count,
        scheduler_running=sched_svc.is_running(),
        last_stm_consolidation=last_stm,
        last_mtm_consolidation=last_mtm,
        last_maintenance=last_maint,
    )


@router.get("/config")
async def get_config_endpoint() -> dict:
    return _redact(get_config())


@router.post("/config")
async def update_config(body: ConfigUpdate) -> dict:
    current = get_config()
    merged = _deep_merge(current, body.config)
    cfg_path = get_config_path()
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, default_flow_style=False, allow_unicode=True)
    load_config()
    return {"updated": True}


@router.post("/consolidate/stm")
async def consolidate_stm() -> dict:
    return await asyncio.to_thread(
        sched_svc.run_and_log, "stm_to_mtm", consolidator.run_stm_to_mtm
    )


@router.post("/consolidate/mtm")
async def consolidate_mtm() -> dict:
    return await asyncio.to_thread(
        sched_svc.run_and_log, "mtm_to_ltm", consolidator.run_mtm_to_ltm
    )


def _redact(cfg: dict) -> dict:
    safe = copy.deepcopy(cfg)
    ai = safe.get("ai_backend", {})
    for backend in ("local", "cloud"):
        if backend in ai and "api_key" in ai[backend]:
            ai[backend]["api_key"] = "***"
    return safe


def _deep_merge(base: dict, updates: dict) -> dict:
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
