# Personal Memory System (PMS)

**Version 0.4.0** — Privacy-first personal memory augmentation layer for Windows

PMS runs as a local Windows service that captures what you read and do, consolidates it with AI, and surfaces relevant context when you ask. All data stays on your machine.

---

## Architecture

```
STM (Short-Term Memory)   — SQLite ring buffer, ~200 events, 24h TTL
MTM (Medium-Term Memory)  — SQLite with Ebbinghaus decay, pinnable episodes
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

> PMS can run without Ollama — retrieval falls back to BM25-only, and consolidation is skipped until AI becomes available.

---

## Installation

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
  watched_extensions: [".txt", ".md", ".py"]
```

### 3. Run the API server

```bat
.venv\Scripts\python.exe -m uvicorn pms.api.main:app --host 127.0.0.1 --port 8765
```

Or use the shortcut:

```bat
.venv\Scripts\python.exe run_api.py
```

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

### `stm`

| Key | Default | Description |
|---|---|---|
| `capacity` | `200` | Ring buffer size (oldest evicted when full) |
| `ttl_hours` | `24` | Hard expiry in hours |

### `mtm`

| Key | Default | Description |
|---|---|---|
| `decay_lambda` | `0.05` | Ebbinghaus forgetting rate λ |
| `decay_threshold` | `1.0` | Score below this → episode deleted |
| `soft_ttl_days` | `90` | Episodes not accessed for this many days are candidates for deletion |

### `consolidation`

| Key | Default | Description |
|---|---|---|
| `stm_trigger_hours` | `6` | STM→MTM consolidation interval |
| `mtm_schedule` | `0 2 * * *` | MTM→LTM cron schedule (default: 2am daily) |
| `min_mtm_score` | `7.0` | Minimum MTM score to qualify for LTM |
| `min_access_count` | `2` | Minimum access count to qualify for LTM |

### `embedding`

| Key | Default | Description |
|---|---|---|
| `backend` | `ollama` | `ollama` or `sentence_transformers` |
| `model` | `nomic-embed-text` | Model name |
| `dim` | `768` | Vector dimension |
| `ollama_url` | `http://localhost:11434` | Ollama base URL |

### `ai`

| Key | Default | Description |
|---|---|---|
| `base_url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `api_key` | `ollama` | API key (ignored by Ollama) |
| `model` | `qwen2.5:7b` | Chat model |

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
{
  "source": "manual",
  "content": "Reviewed the API design document",
  "keywords": "API design review",
  "metadata": {"project": "PMS"}
}
```

### Retrieve

| Method | Path | Description |
|---|---|---|
| `GET` | `/retrieve?q=<query>&limit=10` | Hybrid BM25 + vector search |

**Response:**
```json
{
  "results": [
    {
      "id": "stm:42",
      "source": "manual",
      "content": "Reviewed the API design document",
      "score": 0.87,
      "tier": "stm",
      "created_at": 1714000000.0
    }
  ],
  "partial": false
}
```

`partial: true` means LTM was not searched (embedder unavailable or timed out).

### STM

| Method | Path | Description |
|---|---|---|
| `GET` | `/stm` | List STM events |
| `GET` | `/stm/{id}` | Get one event |
| `DELETE` | `/stm/{id}` | Delete one event |

### MTM

| Method | Path | Description |
|---|---|---|
| `GET` | `/mtm` | List episodes (optional `?min_score=`) |
| `GET` | `/mtm/{id}` | Get one episode |
| `PATCH` | `/mtm/{id}` | Update episode (score, tags, pinned) |
| `DELETE` | `/mtm/{id}` | Delete one episode |

### LTM

| Method | Path | Description |
|---|---|---|
| `GET` | `/ltm` | List concepts |
| `DELETE` | `/ltm/{concept_id}` | Delete a concept |

### Admin

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Service status, last consolidation times |
| `POST` | `/consolidate/stm` | Manually trigger STM→MTM |
| `POST` | `/consolidate/mtm` | Manually trigger MTM→LTM |
| `GET` | `/config` | Show current configuration |
| `PUT` | `/config` | Update configuration at runtime |

---

## Running Tests

```bat
.venv\Scripts\python.exe -m pytest tests/ -v
```

All tests use an isolated temp database and config; Ollama is not required.

---

## Building a Distributable

Requires PyInstaller:

```bat
.venv\Scripts\pip install pyinstaller
build.bat
```

This produces:
- `dist/pms_api.exe` — standalone API server
- `dist/deploy/` — deployment package with NSSM service installer

### Installing as a Windows Service

1. Download [NSSM](https://nssm.cc/download) and add it to `PATH`
2. Copy `dist/deploy/` to your target machine
3. Edit `config.yaml` in the deploy folder
4. Run `install_service.bat` as Administrator

The service starts automatically on Windows boot and listens on `http://127.0.0.1:8765`.

To uninstall: run `uninstall_service.bat` as Administrator.

---

## Development

### Project structure

```
PersonalMemory/
├── pms/
│   └── api/
│       ├── main.py            # FastAPI app + lifespan
│       ├── config.py          # YAML config loader
│       ├── db.py              # SQLite singleton
│       ├── models.py          # Pydantic schemas
│       ├── routers/
│       │   ├── ingest.py
│       │   ├── retrieve.py
│       │   ├── memory.py
│       │   └── admin.py
│       └── services/
│           ├── stm.py
│           ├── mtm.py
│           ├── ltm.py
│           ├── embedder.py
│           ├── consolidator.py
│           ├── scheduler.py
│           ├── browser_poller.py
│           └── file_watcher.py
├── tests/
├── config.yaml
├── requirements.txt
├── run_api.py
├── build.py
├── build_installer.py
├── build.bat
└── app_info.py
```

### Environment variable override

Set `PMS_CONFIG` to point to an alternate `config.yaml`:

```bat
set PMS_CONFIG=C:\custom\pms_config.yaml
.venv\Scripts\python.exe run_api.py
```

---

## License

Private / personal use.

**Author:** Ted Hsieh &lt;ted1966@gmail.com&gt;
