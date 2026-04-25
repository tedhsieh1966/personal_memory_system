# build_installer.py — packages dist/pms_api.exe + dist/pms_editor.exe into dist/deploy/
import os
import shutil
import sys
import textwrap
from pathlib import Path
from app_info import *

ROOT_DIR = str(Path(__file__).parent)
DEPLOY_DIR = os.path.join(ROOT_DIR, DIR_DIST, "deploy")


def build_installer():
    api_exe = os.path.join(ROOT_DIR, DIR_DIST, APP_API_EXE)
    if not os.path.exists(api_exe):
        print(f"Error: {APP_API_EXE} not found in dist/. Run build.py first.")
        return False

    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)
    os.makedirs(DEPLOY_DIR)

    # ── Copy executables ──────────────────────────────────────────────────────
    shutil.copy2(api_exe, DEPLOY_DIR)

    editor_exe = os.path.join(ROOT_DIR, DIR_DIST, APP_EDITOR_EXE)
    has_editor = os.path.exists(editor_exe)
    if has_editor:
        shutil.copy2(editor_exe, DEPLOY_DIR)

    if os.path.exists(FP_CONFIG):
        shutil.copy2(FP_CONFIG, DEPLOY_DIR)

    # ── install_service.bat ───────────────────────────────────────────────────
    with open(os.path.join(DEPLOY_DIR, "install_service.bat"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            @echo off
            :: Run this script as Administrator
            set SVC_NAME={APP_API}
            set EXE_DIR=%~dp0
            set EXE_PATH=%EXE_DIR%{APP_API_EXE}

            where nssm >nul 2>&1
            if %errorlevel% neq 0 (
                echo NSSM not found. Download from https://nssm.cc/download and add to PATH.
                exit /b 1
            )

            echo Installing %SVC_NAME% as a Windows service...
            nssm install %SVC_NAME% "%EXE_PATH%"
            nssm set %SVC_NAME% AppDirectory "%EXE_DIR%"
            nssm set %SVC_NAME% Description "{BRIEF}"
            nssm set %SVC_NAME% Start SERVICE_AUTO_START
            nssm set %SVC_NAME% AppStdout "%EXE_DIR%pms_api.log"
            nssm set %SVC_NAME% AppStderr "%EXE_DIR%pms_api_err.log"
            net start %SVC_NAME%
            echo Done. Service {APP_API} is running on http://127.0.0.1:8765
        """))

    # ── uninstall_service.bat ─────────────────────────────────────────────────
    with open(os.path.join(DEPLOY_DIR, "uninstall_service.bat"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            @echo off
            set SVC_NAME={APP_API}
            echo Stopping and removing %SVC_NAME% service...
            net stop %SVC_NAME%
            nssm remove %SVC_NAME% confirm
            echo Done.
        """))

    # ── launch_editor.bat ─────────────────────────────────────────────────────
    if has_editor:
        with open(os.path.join(DEPLOY_DIR, "launch_editor.bat"), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(f"""\
                @echo off
                start "" "%~dp0{APP_EDITOR_EXE}"
            """))

    # ── README_DEPLOY.txt ─────────────────────────────────────────────────────
    editor_line = f"  {APP_EDITOR_EXE:<30} Desktop editor (launch_editor.bat or double-click)" if has_editor else ""
    with open(os.path.join(DEPLOY_DIR, "README_DEPLOY.txt"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            Personal Memory System (PMS) v{VERSION} — Deployment Package
            ================================================================

            FILES
            -----
              {APP_API_EXE:<30} API server (run as Windows service or standalone)
            {editor_line}
              config.yaml                    Edit BEFORE installing the service
              install_service.bat            Install and start the Windows service (run as Admin)
              uninstall_service.bat          Stop and remove the service (run as Admin)
              launch_editor.bat              Launch the desktop editor

            QUICK START
            -----------
            1. Prerequisites:
               - Download NSSM from https://nssm.cc/download, unzip, add to PATH
               - Install Ollama from https://ollama.com if using local AI
               - Pull required models:  ollama pull qwen2.5:7b
                                        ollama pull nomic-embed-text

            2. Edit config.yaml:
               - Set ingestion.browser_db_paths.chrome to your Chrome History file
               - Set ingestion.watched_dirs to directories you want monitored
               - Adjust ai_backend.local settings if using a different LLM endpoint

            3. Install the service (run as Administrator):
                 install_service.bat
               The API starts automatically and listens on http://127.0.0.1:8765

            4. Launch the editor:
                 launch_editor.bat   (or double-click {APP_EDITOR_EXE})
               Connect to http://127.0.0.1:8765 in the top bar.

            LOGS
            ----
              pms_api.log        Stdout from the API service
              pms_api_err.log    Stderr from the API service

            UNINSTALL
            ---------
            Run uninstall_service.bat as Administrator, then delete this folder.

            SUPPORT
            -------
            Author: {AUTHOR} <{EMAIL}>
        """))

    print(f"Installer package: dist/deploy/")
    print(f"  {APP_API_EXE:<36} API server")
    if has_editor:
        print(f"  {APP_EDITOR_EXE:<36} Desktop editor")
    print(f"  {'config.yaml':<36} Default configuration")
    print(f"  {'install_service.bat':<36} NSSM installer (run as Admin)")
    print(f"  {'uninstall_service.bat':<36} Service remover")
    if has_editor:
        print(f"  {'launch_editor.bat':<36} Editor launcher")
    print(f"  {'README_DEPLOY.txt':<36} Deployment instructions")
    return True


if __name__ == "__main__":
    success = build_installer()
    sys.exit(0 if success else 1)
