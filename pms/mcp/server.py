"""PMS MCP server — exposes remember / recall / memory_status as MCP tools."""
from __future__ import annotations

import json
import logging
import os

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:8765"

server = Server("pms")


def _client() -> httpx.Client:
    base_url = os.environ.get("PMS_URL", _DEFAULT_BASE_URL).rstrip("/")
    return httpx.Client(base_url=base_url, timeout=15.0)


# ── Tool definitions ──────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="remember",
            description=(
                "Store information in the Personal Memory System. "
                "Use this to record anything worth remembering from a conversation, "
                "task, or observation. Content lands in short-term memory and is "
                "automatically consolidated into long-term memory over time."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text to remember.",
                    },
                    "source": {
                        "type": "string",
                        "description": "Who is storing this memory (e.g. 'smartpal', 'claude', 'manual').",
                        "default": "ai",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional key-value metadata (e.g. {\"session\": \"abc\"}).",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="recall",
            description=(
                "Search the Personal Memory System for relevant memories. "
                "Performs a hybrid BM25 + vector search across short-term, "
                "mid-term, and long-term memory tiers. Returns the most relevant "
                "memories ranked by recency and relevance."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="memory_status",
            description=(
                "Return a summary of the Personal Memory System: "
                "event counts across all tiers and last consolidation timestamps. "
                "Useful to check if the memory service is reachable and active."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ── Tool handlers ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent]:
    try:
        if name == "remember":
            return await _remember(arguments)
        if name == "recall":
            return await _recall(arguments)
        if name == "memory_status":
            return await _memory_status()
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    except httpx.ConnectError:
        return [types.TextContent(
            type="text",
            text="PMS API is not reachable. Make sure pms_api is running on "
                 f"{os.environ.get('PMS_URL', _DEFAULT_BASE_URL)}.",
        )]
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return [types.TextContent(type="text", text=f"Error: {exc}")]


async def _remember(args: dict) -> list[types.TextContent]:
    payload: dict = {
        "content": args["content"],
        "source": args.get("source", "ai"),
    }
    if "metadata" in args and args["metadata"]:
        payload["metadata"] = args["metadata"]

    with _client() as client:
        resp = client.post("/ingest", json=payload)
        resp.raise_for_status()
        data = resp.json()

    event_id = data.get("id", "?")
    return [types.TextContent(
        type="text",
        text=f"Remembered (STM event #{event_id}): {args['content'][:120]}",
    )]


async def _recall(args: dict) -> list[types.TextContent]:
    payload = {"query": args["query"], "top_k": args.get("top_k", 10)}

    with _client() as client:
        resp = client.post("/retrieve", json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return [types.TextContent(type="text", text="No memories found.")]

    lines = []
    for r in results:
        tier = r.get("tier", "?").upper()
        score = r.get("score", 0.0)
        content = (r.get("content") or "")[:300]
        lines.append(f"[{tier}  score={score:.2f}]  {content}")

    partial = data.get("partial", False)
    note = "\n(Note: LTM was not searched — embedder unavailable)" if partial else ""
    return [types.TextContent(
        type="text",
        text="\n\n".join(lines) + note,
    )]


async def _memory_status() -> list[types.TextContent]:
    with _client() as client:
        resp = client.get("/status")
        resp.raise_for_status()
        data = resp.json()

    lines = [
        f"STM events:   {data.get('stm_count', '?')}",
        f"MTM episodes: {data.get('mtm_count', '?')}",
        f"LTM concepts: {data.get('ltm_count', '?')}",
        f"Scheduler:    {'running' if data.get('scheduler_running') else 'stopped'}",
        f"Last STM→MTM: {data.get('last_stm_consolidation') or 'never'}",
        f"Last MTM→LTM: {data.get('last_mtm_consolidation') or 'never'}",
    ]
    return [types.TextContent(type="text", text="\n".join(lines))]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
