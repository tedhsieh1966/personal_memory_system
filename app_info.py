import platform
from pathlib import Path

ROOT_DIR = str(Path(__file__).parent)

APP         = "pms"
APP_CAPS    = "PMS"
BRIEF       = "Personal Memory System"
DESCRIPTION = "Privacy-first personal memory augmentation layer for Windows"
VERSION     = "0.3.0"
AUTHOR      = "Ted Hsieh"
EMAIL       = "ted1966@gmail.com"

APP_API     = APP + "_api"
APP_EDITOR  = APP + "_editor"

DIR_DIST    = "dist"
DIR_BUILD   = "build"

system = platform.system()
if system == "Windows":
    SEPARATOR       = ";"
    APP_API_EXE     = APP_API + ".exe"
    APP_EDITOR_EXE  = APP_EDITOR + ".exe"
else:
    SEPARATOR       = ":"
    APP_API_EXE     = APP_API
    APP_EDITOR_EXE  = APP_EDITOR

FP_API_ENTRY  = f"{ROOT_DIR}/run_api.py"
FP_CONFIG     = f"{ROOT_DIR}/config.yaml"
FP_ICON       = f"{ROOT_DIR}/src/favicon.ico"   # placeholder – add icon to src/
