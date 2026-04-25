"""PyInstaller entry point — runs the PMS API server."""
import multiprocessing
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).parent))

import uvicorn
from pms.api.config import get_config, load_config

if __name__ == "__main__":
    multiprocessing.freeze_support()
    load_config()
    cfg = get_config()
    uvicorn.run(
        "pms.api.main:app",
        host=cfg["api"]["host"],
        port=cfg["api"]["port"],
        reload=False,
    )
