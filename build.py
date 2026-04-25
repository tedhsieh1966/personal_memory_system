# build.py — PyInstaller build for pms_api.exe
import os
import shutil
import platform
import PyInstaller.__main__
from app_info import *


def build():
    if platform.system() != "Windows":
        print("PMS is Windows-only. Build must run on Windows.")
        return False

    for d in [DIR_DIST, DIR_BUILD]:
        if os.path.exists(d):
            shutil.rmtree(d)

    print(f"Building {APP_API_EXE}...")

    args = [
        FP_API_ENTRY,
        "--onefile",
        "--console",
        f"--name={APP_API}",
        f"--add-data={FP_CONFIG}{SEPARATOR}.",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=pms.api.main",
        "--hidden-import=pms.api.routers.ingest",
        "--hidden-import=pms.api.routers.retrieve",
        "--hidden-import=pms.api.routers.memory",
        "--hidden-import=pms.api.routers.admin",
        "--hidden-import=pms.api.services.stm",
        "--hidden-import=pms.api.services.mtm",
        "--hidden-import=pms.api.services.ltm",
        "--hidden-import=pms.api.services.embedder",
        "--hidden-import=pms.api.services.consolidator",
        "--hidden-import=pms.api.services.scheduler",
        "--hidden-import=pms.api.services.browser_poller",
        "--hidden-import=pms.api.services.file_watcher",
        "--hidden-import=apscheduler.schedulers.asyncio",
        "--hidden-import=apscheduler.triggers.cron",
        "--hidden-import=apscheduler.triggers.interval",
        "--hidden-import=watchdog.observers",
        "--hidden-import=watchdog.observers.winapi",
        "--hidden-import=watchdog.events",
        "--hidden-import=lancedb",
        "--hidden-import=pyarrow",
        "--hidden-import=openai",
        "--distpath=dist",
        "--workpath=build",
        "--noconfirm",
    ]

    if os.path.exists(FP_ICON):
        args.append(f"--icon={FP_ICON}")

    try:
        PyInstaller.__main__.run(args)
        print(f"Build complete: dist/{APP_API_EXE}")
        return True
    except Exception as e:
        print(f"Build failed: {e}")
        return False


if __name__ == "__main__":
    success = build()
    exit(0 if success else 1)
