from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .config import get_config, load_config
from .db import get_conn
from .routers import admin, ingest, memory, retrieve
from .services import file_watcher as fw_svc
from .services import ltm as ltm_svc
from .services import scheduler as sched_svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_config()
    get_conn()
    ltm_svc.init()
    sched_svc.start()
    fw_svc.start()
    yield
    fw_svc.stop()
    sched_svc.stop()


app = FastAPI(
    title="Personal Memory System API",
    version="0.4.0",
    description="Privacy-first personal memory augmentation layer for Windows",
    lifespan=lifespan,
)

app.include_router(ingest.router)
app.include_router(retrieve.router)
app.include_router(memory.router)
app.include_router(admin.router)


if __name__ == "__main__":
    load_config()
    cfg = get_config()
    uvicorn.run(
        "pms.api.main:app",
        host=cfg["api"]["host"],
        port=cfg["api"]["port"],
        reload=False,
    )
