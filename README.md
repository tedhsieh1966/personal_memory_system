# Personal Memory System (PMS)

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Version](https://img.shields.io/badge/version-0.6.0-green)
![License](https://img.shields.io/badge/license-private-lightgrey)

**Your personal AI memory — running entirely on your own machine.**

PMS quietly learns from what you read, write, and talk about. Ask it anything and it surfaces the right context — from this morning's browser tabs or last month's notes. No cloud. No subscriptions. No data leaves your PC.

---

## Why PMS?

Most AI assistants forget everything the moment you close the chat. PMS gives any AI — or your own apps — a persistent, searchable memory that grows smarter over time.

- **SmartPal had a conversation last Tuesday?** PMS remembers it.
- **You read an article about Rust three weeks ago?** PMS can surface it.
- **Your AI assistant needs context before answering?** It calls `recall` and knows.

---

## Key Features

- **Three-tier memory** — Short-term (hours) → Mid-term (weeks) → Long-term (permanent concepts), each with automatic promotion
- **AI consolidation** — Raw events are summarised into episodes; episodes are distilled into durable concepts using a local LLM (Ollama / any OpenAI-compatible endpoint)
- **Ebbinghaus forgetting** — Mid-term memories decay naturally unless accessed; pinned episodes are preserved
- **Hybrid search** — BM25 keyword search + vector similarity search, combined and ranked by recency
- **Browser ingestion** — Automatically indexes Chrome and Firefox history in the background
- **File watching** — Monitors directories for new/changed documents and ingests them
- **Desktop editor** — Full CustomTkinter GUI to browse, search, pin, delete, and export memories
- **REST API + Skill** — Any app or AI can call `POST /ingest` and `POST /retrieve` — see [skill.md](skill.md)
- **Windows service** — Runs silently at startup via NSSM; zero maintenance

---

## Screenshots

> *Coming soon — editor screenshots and demo GIF*

---

## Quick Start

**Prerequisites:** Windows 10/11 · Python 3.11+ · 8 GB RAM (16 GB recommended) · [Ollama](https://ollama.com) optional but recommended for AI consolidation · NVIDIA GPU with 6 GB+ VRAM for fast local inference

```bat
git clone <repo>
cd PersonalMemory
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

Start the API:
```bat
.venv\Scripts\python.exe run_api.py
```

Launch the editor:
```bat
.venv\Scripts\python.exe run_editor.py
```

> PMS works without Ollama — retrieval falls back to keyword search and AI consolidation is skipped until a model is available.

---

## Integrating with Other Apps

Any app or AI can use PMS memory with two HTTP calls:

```python
import httpx

# Store a memory
httpx.post("http://127.0.0.1:8765/ingest", json={
    "source": "myapp",
    "content": "User prefers dark mode and short meetings."
})

# Search memories
results = httpx.post("http://127.0.0.1:8765/retrieve", json={
    "query": "user preferences"
}).json()
```

See [skill.md](skill.md) for the full integration guide including request/response shapes, examples, and caller guidance for AI assistants.

---

## Documentation

| Document | Contents |
|---|---|
| [USER_MANUAL.md](USER_MANUAL.md) | Full setup guide, editor walkthrough, configuration explained, troubleshooting |
| [skill.md](skill.md) | API integration descriptor for apps and AI assistants |
| [config.yaml](config.yaml) | Annotated default configuration |

---

## Project Structure

```
PersonalMemory/
├── pms/
│   ├── api/          # FastAPI service (STM/MTM/LTM, consolidation, ingestion)
│   ├── editor/       # CustomTkinter desktop GUI
│   └── mcp/          # MCP stdio server
├── tests/            # 110 tests, no Ollama required
├── skill.md          # Integration descriptor
├── USER_MANUAL.md    # Full user manual
├── run_api.py        # Start the API server
├── run_editor.py     # Launch the desktop editor
├── run_mcp.py        # Start the MCP server
├── build.bat         # Build distributable exes + deploy package
└── config.yaml       # Configuration
```

---

## License

Private / personal use.
**Author:** Ted Hsieh &lt;ted1966@gmail.com&gt;
