# Personal Memory System (PMS)

**Version 0.6.0** — Privacy-first personal memory augmentation layer for Windows

PMS runs as a local Windows service that captures what you read and do, consolidates it with AI, and surfaces relevant context when you ask. All data stays on your machine.

---

## Architecture

```
STM (Short-Term Memory)   — SQLite ring buffer, ~500 events, 12h TTL
MTM (Mid-Term Memory)     — SQLite with Ebbinghaus decay, pinnable episodes
LTM (Long-Term Memory)    — LanceDB vector store, permanent concept distillation
```

Events flow upward automatically:

1. **Ingest** — browser history, file changes, and manual `/ingest` calls land in STM
2. **STM → MTM** — AI summarises batches of raw events into episodes (every 6h or at 80% capacity)
3. **MTM → LTM** — high-confidence episodes are distilled to concept embeddings (nightly cron)
4. **Retrieve** — BM25 search over STM+MTM combined with vector search over LTM

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| Ollama | For embeddings and AI consolidation |
| `qwen2.5:7b` model | `ollama pull qwen2.5:7b` |
| `nomic-embed-text` model | `ollama pull nomic-embed-text` |

> PMS degrades gracefully without Ollama — retrieval falls back to BM25-only and consolidation is skipped until AI becomes available.

---

## Installation (development)

### 1. Clone and set up the virtual environment

```bat
git clone <repo>
cd PersonalMemory
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml` to set your browser database paths and watched directories:

```yaml
ingestion:
  browser_db_paths:
    chrome: "C:/Users/YourName/AppData/Local/Google/Chrome/User Data/Default/History"
    firefox: "C:/Users/YourName/AppData/Roaming/Mozilla/Firefox/Profiles"
  watched_dirs:
    - "C:/Users/YourName/Documents"

ai_backend:
  provider: "local"
  local:
    base_url: "http://localhost:11434/v1"
    api_key: "ollama"
    model: "qwen2.5:7b"
```

### 3. Run the API server

```bat
.venv\Scripts\python.exe run_api.py
```

### 4. Launch the editor

```bat
.venv\Scripts\python.exe run_editor.py
```

Connect to `http://127.0.0.1:8765` using the top bar.

### 5. (Optional) Run the MCP server

```bat
.venv\Scripts\python.exe run_mcp.py
```

Exposes `remember`, `recall`, and `memory_status` as MCP tools over stdio. See the [AI / App Integration](#ai--app-integration) section below.

---

## Configuration Reference (`config.yaml`)

### `api`

| Key | Default | Description |
|---|---|---|
| `host` | `127.0.0.1` | Bind address |
| `port` | `8765` | Bind port |

### `storage`

| Key | Default | Description |
|---|---|---|
| `db_path` | `pms.db` | SQLite database file |
| `ltm_path` | `pms_ltm` | LanceDB directory |

### `memory`

| Key | Default | Description |
|---|---|---|
| `stm_capacity` | `500` | Ring buffer size (oldest evicted when full) |
| `stm_ttl_hours` | `12` | Hard expiry in hours |
| `mtm_decay_lambda` | `0.05` | Ebbinghaus forgetting rate λ |
| `mtm_score_threshold` | `1.0` | Score below this → episode deleted |
| `mtm_ttl_days` | `21` | Episodes not accessed for this many days are deletion candidates |

### `consolidation`

| Key | Default | Description |
|---|---|---|
| `stm_trigger_hours` | `6` | STM→MTM consolidation interval |
| `mtm_schedule` | `0 2 * * 0` | MTM→LTM cron schedule |

### `embedding`

| Key | Default | Description |
|---|---|---|
| `provider` | `ollama` | `ollama` or `sentence_transformers` |
| `model` | `nomic-embed-text` | Model name |
| `dim` | `768` | Vector dimension |
| `ollama_url` | `http://localhost:11434` | Ollama base URL |

### `ai_backend`

| Key | Default | Description |
|---|---|---|
| `provider` | `local` | `local` or `cloud` |
| `local.base_url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `local.api_key` | `ollama` | API key |
| `local.model` | `qwen2.5:7b` | Chat model |

### `ingestion`

| Key | Default | Description |
|---|---|---|
| `browser_db_paths.chrome` | *(empty)* | Path to Chrome `History` SQLite file |
| `browser_db_paths.firefox` | *(empty)* | Path to Firefox `Profiles` directory |
| `browser_poll_interval_min` | `30` | How often to poll browser history |
| `watched_dirs` | `[]` | Directories to monitor for file changes |
| `watched_extensions` | `[]` | File extensions to ingest (empty = all) |

---

## REST API Reference

Base URL: `http://127.0.0.1:8765`

### Ingest

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a new event into STM |

**Request body:**
```json
{ "source": "manual", "content": "Reviewed the API design document" }
```

### Retrieve

| Method | Path | Description |
|---|---|---|
| `POST` | `/retrieve` | Hybrid BM25 + vector search |

**Request body:**
```json
{ "query": "API design", "top_k": 10 }
```

### Memory

| Method | Path | Description |
|---|---|---|
| `GET` | `/memory/stm` | List STM events |
| `DELETE` | `/memory/stm/{id}` | Delete an STM event |
| `GET` | `/memory/mtm` | List MTM episodes |
| `PATCH` | `/memory/mtm/{id}` | Update episode (`pinned`, `importance_score`) |
| `DELETE` | `/memory/mtm/{id}` | Delete an episode |
| `GET` | `/memory/ltm` | List LTM concepts |
| `DELETE` | `/memory/ltm/{id}` | Delete a concept |

### Admin

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Counts + last consolidation times |
| `POST` | `/consolidate/stm` | Manually trigger STM→MTM |
| `POST` | `/consolidate/mtm` | Manually trigger MTM→LTM |
| `GET` | `/config` | Show current configuration |
| `POST` | `/config` | Update configuration at runtime |

---

## AI / App Integration

Any application or AI assistant can call PMS over plain HTTP — no special SDK required.

See **[skill.md](skill.md)** for the full integration guide: operations, request/response shapes, examples, and caller guidance.

### Quick reference

| Goal | Call |
|---|---|
| Store a memory | `POST /ingest` with `content` + `source` |
| Search memories | `POST /retrieve` with `query` |
| Check service health | `GET /status` |

### MCP server (for AI assistants)

If your AI framework supports MCP, run the included stdio server:

```bat
.venv\Scripts\python.exe run_mcp.py
```

Set `PMS_URL` env var to override the default `http://127.0.0.1:8765`.

---

## Running Tests

```bat
.venv\Scripts\python.exe -m pytest tests/ -q
```

All tests use an isolated temp database; Ollama is not required.

---

## Building a Distributable

```bat
build.bat
```

Produces:
- `dist/pms_api.exe` — standalone API server
- `dist/pms_editor.exe` — desktop editor
- `dist/deploy/` — deployment package with NSSM service scripts, editor, and instructions

### Installing as a Windows Service

1. Download [NSSM](https://nssm.cc/download) and add it to `PATH`
2. Copy `dist/deploy/` to the target machine
3. Edit `config.yaml` in the deploy folder
4. Run `install_service.bat` as Administrator
5. Launch `pms_editor.exe` to manage memories

The service starts automatically on Windows boot and listens on `http://127.0.0.1:8765`.

---

## Project Structure

```
PersonalMemory/
├── pms/
│   ├── api/
│   │   ├── main.py            # FastAPI app + lifespan
│   │   ├── config.py          # YAML config loader
│   │   ├── db.py              # SQLite singleton
│   │   ├── models.py          # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── ingest.py
│   │   │   ├── retrieve.py
│   │   │   ├── memory.py
│   │   │   └── admin.py
│   │   └── services/
│   │       ├── stm.py
│   │       ├── mtm.py
│   │       ├── ltm.py
│   │       ├── embedder.py
│   │       ├── consolidator.py
│   │       ├── scheduler.py
│   │       ├── browser_poller.py
│   │       └── file_watcher.py
│   ├── editor/
│   │   ├── app.py             # CustomTkinter main window
│   │   ├── api_client.py      # httpx REST client
│   │   └── views/
│   │       ├── dashboard.py
│   │       ├── stm_view.py
│   │       ├── mtm_view.py
│   │       ├── ltm_view.py
│   │       ├── settings_view.py
│   │       └── log_view.py
│   └── mcp/
│       └── server.py          # MCP stdio server (remember/recall/memory_status)
├── tests/
├── skill.md                   # AI/app integration descriptor
├── config.yaml
├── requirements.txt
├── pyproject.toml
├── run_api.py
├── run_editor.py
├── run_mcp.py
├── build.py
├── build_installer.py
├── build.bat
└── app_info.py
```

---

## Environment Variable Override

Set `PMS_CONFIG` to point to an alternate `config.yaml`:

```bat
set PMS_CONFIG=C:\custom\pms_config.yaml
.venv\Scripts\python.exe run_api.py
```

---

## License

Private / personal use.  
**Author:** Ted Hsieh &lt;ted1966@gmail.com&gt;
