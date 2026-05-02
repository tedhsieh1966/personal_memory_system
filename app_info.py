import platform
from pathlib import Path

ROOT_DIR = str(Path(__file__).parent)

APP         = "pms"
APP_CAPS    = "PMS"
BRIEF       = "Personal Memory System"
DESCRIPTION = "Privacy-first personal memory augmentation layer for Windows"
VERSION     = "0.6.0"
AUTHOR      = "Ted Hsieh"
EMAIL       = "ted1966@gmail.com"

APP_SERVER      = APP + "_server"
APP_EDITOR      = APP + "_editor"
APP_INSTALLER   = APP + "_installer"
APP_MANAGER     = APP + "_manager"

DIR_DIST    = "dist"
DIR_BUILD   = "build"

system = platform.system()
if system == "Windows":
    SEPARATOR           = ";"
    APP_SERVER_EXE      = APP_SERVER + ".exe"
    APP_EDITOR_EXE      = APP_EDITOR + ".exe"
    APP_INSTALLER_EXE   = APP_INSTALLER + ".exe"
    APP_MANAGER_EXE     = APP_MANAGER + ".exe"
else:
    SEPARATOR           = ":"
    APP_SERVER_EXE      = APP_SERVER
    APP_EDITOR_EXE      = APP_EDITOR
    APP_INSTALLER_EXE   = APP_INSTALLER
    APP_MANAGER_EXE     = APP_MANAGER

APP_DESKTOP_LINK = APP_CAPS + " Editor.lnk"

FP_SERVER_ENTRY     = f"{ROOT_DIR}/run_server.py"
FP_LANGUAGES        = f"{ROOT_DIR}/pms/editor/languages.xlsx"
FP_EDITOR_ENTRY     = f"{ROOT_DIR}/run_editor.py"
FP_MCP_ENTRY        = f"{ROOT_DIR}/run_mcp.py"
FP_INSTALLER_ENTRY  = f"{ROOT_DIR}/installer.py"
FP_MANAGER_ENTRY    = f"{ROOT_DIR}/manager.py"
FP_CONFIG           = f"{ROOT_DIR}/config.yaml"
FP_NSSM             = f"{ROOT_DIR}/nssm.exe"          # vendored, bundled into installer
FP_ICON             = f"{ROOT_DIR}/src/favicon.ico"   # placeholder – add icon to src/
