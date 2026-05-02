# build.py — PyInstaller builds for pms_server.exe and pms_editor.exe
import os
import shutil
import platform
import PyInstaller.__main__
from app_info import *


def _icon_arg() -> list[str]:
    return [f"--icon={FP_ICON}"] if os.path.exists(FP_ICON) else []


def build_server() -> bool:
    print(f"Building {APP_SERVER_EXE}...")
    args = [
        FP_SERVER_ENTRY,
        "--onefile",
        "--console",
        f"--name={APP_SERVER}",
        f"--add-data={FP_CONFIG}{SEPARATOR}.",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=pms.server.main",
        "--hidden-import=pms.server.routers.ingest",
        "--hidden-import=pms.server.routers.retrieve",
        "--hidden-import=pms.server.routers.memory",
        "--hidden-import=pms.server.routers.admin",
        "--hidden-import=pms.service.stm",
        "--hidden-import=pms.service.mtm",
        "--hidden-import=pms.service.ltm",
        "--hidden-import=pms.service.embedder",
        "--hidden-import=pms.service.consolidator",
        "--hidden-import=pms.service.scheduler",
        "--hidden-import=pms.service.browser_poller",
        "--hidden-import=pms.service.file_watcher",
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
    ] + _icon_arg()
    try:
        PyInstaller.__main__.run(args)
        print(f"  -> dist/{APP_SERVER_EXE}")
        return True
    except Exception as e:
        print(f"Server build failed: {e}")
        return False


def build_editor() -> bool:
    print(f"Building {APP_EDITOR_EXE}...")
    args = [
        FP_EDITOR_ENTRY,
        "--onefile",
        "--windowed",
        f"--name={APP_EDITOR}",
        f"--add-data={FP_LANGUAGES}{SEPARATOR}.",
        "--hidden-import=pms.editor.app",
        "--hidden-import=pms.editor.api_client",
        "--hidden-import=pms.editor.i18n",
        "--hidden-import=pms.editor.prefs",
        "--hidden-import=pms.editor.views",
        "--hidden-import=pms.editor.views.dashboard",
        "--hidden-import=pms.editor.views.stm_view",
        "--hidden-import=pms.editor.views.mtm_view",
        "--hidden-import=pms.editor.views.ltm_view",
        "--hidden-import=pms.editor.views.settings_view",
        "--hidden-import=pms.editor.views.log_view",
        "--hidden-import=customtkinter",
        "--hidden-import=httpx",
        "--hidden-import=py_libraries",
        "--hidden-import=py_libraries.LanguageOp",
        "--hidden-import=pandas",
        "--hidden-import=openpyxl",
        "--collect-all=customtkinter",
        "--collect-all=py_libraries",
        "--distpath=dist",
        "--workpath=build",
        "--noconfirm",
    ] + _icon_arg()
    try:
        PyInstaller.__main__.run(args)
        print(f"  -> dist/{APP_EDITOR_EXE}")
        return True
    except Exception as e:
        print(f"Editor build failed: {e}")
        return False


def build_manager() -> bool:
    print(f"Building {APP_MANAGER_EXE}...")
    args = [
        FP_MANAGER_ENTRY,
        "--onefile",
        "--console",
        f"--name={APP_MANAGER}",
        "--distpath=dist",
        "--workpath=build",
        "--noconfirm",
    ] + _icon_arg()
    try:
        PyInstaller.__main__.run(args)
        print(f"  -> dist/{APP_MANAGER_EXE}")
        return True
    except Exception as e:
        print(f"Manager build failed: {e}")
        return False


def build() -> bool:
    if platform.system() != "Windows":
        print("PMS is Windows-only. Build must run on Windows.")
        return False

    for d in [DIR_DIST, DIR_BUILD]:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
            except PermissionError:
                print(f"Warning: could not clean {d} (in use) — reusing existing directory.")

    ok_server  = build_server()
    ok_editor  = build_editor()
    ok_manager = build_manager()
    return ok_server and ok_editor and ok_manager


if __name__ == "__main__":
    success = build()
    exit(0 if success else 1)
