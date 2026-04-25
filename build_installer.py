# build_installer.py — packages dist/pms_api.exe + NSSM service scripts
import os
import shutil
import sys
import textwrap
from pathlib import Path
from app_info import *

ROOT_DIR = str(Path(__file__).parent)
DEPLOY_DIR = os.path.join(ROOT_DIR, DIR_DIST, "deploy")


def build_installer():
    exe_path = os.path.join(ROOT_DIR, DIR_DIST, APP_API_EXE)
    if not os.path.exists(exe_path):
        print(f"Error: {APP_API_EXE} not found in dist/. Run build.py first.")
        return False

    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)
    os.makedirs(DEPLOY_DIR)

    shutil.copy2(exe_path, DEPLOY_DIR)

    editor_path = os.path.join(ROOT_DIR, DIR_DIST, APP_EDITOR_EXE)
    if os.path.exists(editor_path):
        shutil.copy2(editor_path, DEPLOY_DIR)

    if os.path.exists(FP_CONFIG):
        shutil.copy2(FP_CONFIG, DEPLOY_DIR)

    install_bat = os.path.join(DEPLOY_DIR, "install_service.bat")
    with open(install_bat, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            @echo off
            :: Run this script as Administrator
            set SVC_NAME={APP_API}
            set EXE_DIR=%~dp0
            set EXE_PATH=%EXE_DIR%{APP_API_EXE}

            where nssm >nul 2>&1
            if %errorlevel% neq 0 (
                echo NSSM not found. Download from https://nssm.cc/download and add it to PATH.
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

    uninstall_bat = os.path.join(DEPLOY_DIR, "uninstall_service.bat")
    with open(uninstall_bat, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            @echo off
            set SVC_NAME={APP_API}
            echo Stopping and removing %SVC_NAME% service...
            net stop %SVC_NAME%
            nssm remove %SVC_NAME% confirm
            echo Done.
        """))

    print(f"Installer package created in dist/deploy/")
    print(f"  {APP_API_EXE:<30} API server executable")
    print(f"  {'config.yaml':<30} default configuration (edit before installing)")
    print(f"  {'install_service.bat':<30} NSSM service installer (run as Administrator)")
    print(f"  {'uninstall_service.bat':<30} service uninstaller")
    return True


if __name__ == "__main__":
    success = build_installer()
    sys.exit(0 if success else 1)
