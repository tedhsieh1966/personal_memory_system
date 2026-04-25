"""Entry point for the PMS MCP server (stdio transport).

Usage:
    python run_mcp.py

Environment:
    PMS_URL  — base URL of the PMS API (default: http://127.0.0.1:8765)

Claude Desktop / Claude Code config:
    {
      "mcpServers": {
        "pms": {
          "command": "C:/Projects/Python/PersonalMemory/.venv/Scripts/python.exe",
          "args": ["C:/Projects/Python/PersonalMemory/run_mcp.py"],
          "env": { "PMS_URL": "http://127.0.0.1:8765" }
        }
      }
    }
"""
import asyncio
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).parent))

from pms.mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
