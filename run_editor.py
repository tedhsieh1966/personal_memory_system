"""PyInstaller entry point — launches the PMS Editor desktop application."""
import multiprocessing
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).parent))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from pms.editor.app import run
    run()
