# manager.py — PMS service manager CLI
#
# Usage:
#   pms_manager <command> [options]
#
# Commands:
#   start                  Start the pms_server Windows service
#   stop                   Stop the pms_server Windows service
#   restart                Restart the pms_server Windows service
#   status                 Show service state and API health
#   consolidate [stm|mtm]  Trigger consolidation (default: stm)
#   log [n]                Print the last n lines of pms_server.log (default: 50)
#
# Commands may be prefixed with - or -- (e.g. -start, --start).

import sys
import os
import shutil
import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from app_info import *

INSTALL_DIR = Path(os.getenv("APPDATA")) / APP
API_BASE    = "http://127.0.0.1:8765"
LOG_FILE    = INSTALL_DIR / "pms_server.log"
OLLAMA_EXE  = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"


# ── service control ───────────────────────────────────────────────────────────

def svc_start():
    print(f"Starting {APP_SERVER} service…")
    r = subprocess.run(["net", "start", APP_SERVER], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(out if out else "Done.")
    return r.returncode == 0


def svc_stop():
    print(f"Stopping {APP_SERVER} service…")
    r = subprocess.run(["net", "stop", APP_SERVER], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(out if out else "Done.")
    return r.returncode == 0


def svc_restart():
    svc_stop()
    svc_start()


def svc_state():
    """Return 'running', 'stopped', or 'unknown'."""
    r = subprocess.run(
        ["sc", "query", APP_SERVER],
        capture_output=True, text=True
    )
    text = r.stdout.lower()
    if "running" in text:
        return "running"
    if "stopped" in text:
        return "stopped"
    if r.returncode != 0:
        return "not installed"
    return "unknown"


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(path):
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError:
        return None


def api_post(path):
    try:
        req = urllib.request.Request(f"{API_BASE}{path}", data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError:
        return None


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_status():
    state = svc_state()
    color = "\033[32m" if state == "running" else "\033[31m"
    reset = "\033[0m"
    print(f"\nService : {color}{state}{reset}")

    data = api_get("/status")
    if data:
        mem = data.get("memory", {})
        last = data.get("last_consolidation", {})
        print(f"API     : reachable at {API_BASE}")
        print(f"STM     : {mem.get('stm', '?')} events")
        print(f"MTM     : {mem.get('mtm', '?')} episodes")
        print(f"LTM     : {mem.get('ltm', '?')} concepts")
        stm_ts = last.get("stm_to_mtm") or "never"
        mtm_ts = last.get("mtm_to_ltm") or "never"
        print(f"Last consolidation  STM→MTM: {stm_ts}   MTM→LTM: {mtm_ts}")
    else:
        print(f"API     : \033[31mnot reachable\033[0m ({API_BASE})")
    print()


def cmd_consolidate(tier="stm"):
    tier = tier.lower()
    if tier not in ("stm", "mtm"):
        print(f"Unknown tier '{tier}'. Use 'stm' or 'mtm'.")
        sys.exit(1)
    endpoint = f"/consolidate/{tier}"
    print(f"Triggering {tier.upper()} consolidation…")
    result = api_post(endpoint)
    if result is None:
        print("Error: API not reachable.")
        sys.exit(1)
    print(json.dumps(result, indent=2))


def cmd_log(n=50):
    try:
        n = int(n)
    except ValueError:
        print(f"Invalid line count: {n}")
        sys.exit(1)

    if not LOG_FILE.exists():
        print(f"Log file not found: {LOG_FILE}")
        sys.exit(1)

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for line in lines[-n:]:
        print(line, end="")


# ── Ollama control ────────────────────────────────────────────────────────────

def _find_ollama() -> str | None:
    return shutil.which("ollama") or (str(OLLAMA_EXE) if OLLAMA_EXE.exists() else None)


def cmd_ollama_start():
    ollama = _find_ollama()
    if not ollama:
        print("Ollama not found. Install it from https://ollama.com")
        sys.exit(1)
    print("Starting Ollama...")
    subprocess.Popen(
        [ollama, "serve"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("Ollama started (serving on http://localhost:11434)")


def cmd_ollama_stop():
    r = subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode == 0:
        print("Ollama stopped.")
    else:
        print(f"Could not stop Ollama: {out}")


# ── entry point ───────────────────────────────────────────────────────────────

COMMANDS = {
    "start":        lambda args: svc_start(),
    "stop":         lambda args: svc_stop(),
    "restart":      lambda args: svc_restart(),
    "status":       lambda args: cmd_status(),
    "consolidate":  lambda args: cmd_consolidate(args[0] if args else "stm"),
    "log":          lambda args: cmd_log(args[0] if args else 50),
    "ollama-start": lambda args: cmd_ollama_start(),
    "ollama-stop":  lambda args: cmd_ollama_stop(),
}

HELP = f"""\
{APP_CAPS} Manager v{VERSION}

Usage: {APP_MANAGER} <command> [options]

Commands:
  start                   Start the PMS server Windows service
  stop                    Stop the PMS server Windows service
  restart                 Restart the PMS server Windows service
  status                  Show service state and server health
  consolidate [stm|mtm]   Trigger AI consolidation (default: stm)
  log [n]                 Print last n log lines (default: 50)
  ollama-start            Start Ollama in the background (ollama serve)
  ollama-stop             Stop the Ollama process

Commands may be prefixed with - or -- (e.g. -start, --start).
"""


def main():
    argv = sys.argv[1:]
    if not argv or argv[0].lstrip("-").lower() in ("help", "h", "?"):
        print(HELP)
        sys.exit(0)

    cmd  = argv[0].lstrip("-").lower()
    args = argv[1:]

    if cmd not in COMMANDS:
        print(f"Unknown command: {argv[0]}\n")
        print(HELP)
        sys.exit(1)

    COMMANDS[cmd](args)


if __name__ == "__main__":
    main()
