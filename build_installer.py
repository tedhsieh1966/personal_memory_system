# build_installer.py — bundles pms_api.exe + pms_editor.exe + config.yaml into pms_installer.exe
import os
import sys
import platform
import PyInstaller.__main__
from pathlib import Path

ROOT_DIR = str(Path(__file__).parent)
sys.path.insert(0, ROOT_DIR)
from app_info import *


def build_installer():
    if platform.system() != "Windows":
        print("PMS installer can only be built on Windows.")
        return False

    api_exe     = os.path.join(ROOT_DIR, DIR_DIST, APP_API_EXE)
    editor_exe  = os.path.join(ROOT_DIR, DIR_DIST, APP_EDITOR_EXE)
    manager_exe = os.path.join(ROOT_DIR, DIR_DIST, APP_MANAGER_EXE)

    for path, name in [(api_exe, APP_API_EXE), (editor_exe, APP_EDITOR_EXE), (manager_exe, APP_MANAGER_EXE)]:
        if not os.path.exists(path):
            print(f"Error: {name} not found in dist/. Run build.py first.")
            return False

    print(f"Building {APP_INSTALLER_EXE}...")

    args = [
        FP_INSTALLER_ENTRY,
        "--onefile",
        "--windowed",
        f"--name={APP_INSTALLER}",
        f"--add-data={api_exe}{SEPARATOR}.",
        f"--add-data={editor_exe}{SEPARATOR}.",
        f"--add-data={manager_exe}{SEPARATOR}.",
        f"--add-data={FP_CONFIG}{SEPARATOR}.",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=win32com.server",
        "--noconfirm",
        "--clean",
        f"--distpath={os.path.join(ROOT_DIR, DIR_DIST)}",
        f"--workpath={os.path.join(ROOT_DIR, DIR_BUILD)}",
    ]

    if os.path.exists(FP_ICON):
        args.append(f"--icon={FP_ICON}")

    try:
        PyInstaller.__main__.run(args)
        print(f"  -> dist/{APP_INSTALLER_EXE}")
        return True
    except Exception as e:
        print(f"Installer build failed: {e}")
        return False


if __name__ == "__main__":
    success = build_installer()
    sys.exit(0 if success else 1)
