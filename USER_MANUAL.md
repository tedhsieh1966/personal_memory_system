# PMS User Manual

**Personal Memory System v0.6.0**

This manual covers everything from initial setup to day-to-day use. It explains *why* things work the way they do, not just *how* to configure them.

---

## Table of Contents

1. [How PMS Works](#1-how-pms-works)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Running the API Server](#5-running-the-api-server)
6. [Using the Desktop Editor](#6-using-the-desktop-editor)
7. [Browser History Ingestion](#7-browser-history-ingestion)
8. [File Watching](#8-file-watching)
9. [AI Consolidation](#9-ai-consolidation)
10. [Integrating Other Apps](#10-integrating-other-apps)
11. [Building a Distributable](#11-building-a-distributable)
12. [Installing as a Windows Service](#12-installing-as-a-windows-service)
13. [Configuration Reference](#13-configuration-reference)
14. [REST API Reference](#14-rest-api-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. How PMS Works

PMS organises your personal memory into three tiers, each suited to a different time horizon.

### Short-Term Memory (STM)

STM is a ring buffer of raw events — every URL you visit, every file you change, every piece of text ingested manually. It holds up to 500 events and expires them after 12 hours by default. Think of it as RAM: fast, abundant, but short-lived.

### Mid-Term Memory (MTM)

Every few hours, PMS asks a local AI to read a batch of STM events and write a concise *episode* — a summary of what you were doing and why it might matter. Episodes live in MTM for up to 21 days, but they don't just age passively: PMS applies an Ebbinghaus forgetting curve. Events you revisit frequently stay; things you never touch again gradually fade. You can *pin* important episodes to stop them from decaying.

### Long-Term Memory (LTM)

Once a week (or on demand), PMS distils the highest-scoring MTM episodes into durable *concepts* stored as vector embeddings in a LanceDB database. These are things like "the user is building a Python memory system" or "the user prefers functional programming style." Concepts persist indefinitely and are recalled via semantic vector search.

### The Retrieve Flow

When you (or an app) searches for something, PMS runs two searches in parallel:

- **BM25 keyword search** over STM and MTM — fast, works without AI
- **Vector similarity search** over LTM — semantic, requires the embedder

Results from both are merged, de-duplicated, and re-ranked by a combination of relevance score and recency. If the embedder is unavailable, PMS returns keyword results only (marked `partial: true`).

---

## 2. Prerequisites

| Requirement | Why it's needed |
|---|---|
| **Windows 10/11** | File watcher and browser poller use Windows-specific paths |
| **Python 3.11+** | Required by FastAPI and LanceDB |
| **Ollama** | Runs the local LLM for AI consolidation and the embedding model for LTM search |
| **qwen2.5:7b** | The chat model used to summarise events and distil concepts |
| **nomic-embed-text** | The embedding model used to convert text into LTM vectors |

**Ollama is optional.** If it isn't running, PMS degrades gracefully:
- STM and MTM still work fully (keyword search, ingest, browse)
- LTM search is skipped (results marked `partial: true`)
- AI consolidation is skipped until Ollama becomes available

Install Ollama from [ollama.com](https://ollama.com), then pull the models:

```bat
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

## 3. Installation

### Clone and create a virtual environment

```bat
git clone <repo>
cd PersonalMemory
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

The virtual environment keeps PMS dependencies isolated from the rest of your system.

### Verify the installation

```bat
.venv\Scripts\python.exe -m pytest tests/ -q
```

All 110 tests should pass. Ollama does not need to be running for the tests.

---

## 4. Configuration

All settings live in `config.yaml` in the project root. The file is human-readable YAML — edit it with any text editor before starting the API.

### The most important settings to change

#### Browser paths

PMS needs to know where your browser stores its history database. The defaults use Windows environment variables (`%LOCALAPPDATA%`, `%APPDATA%`) which usually resolve correctly, but if you have a non-standard profile, set them explicitly:

```yaml
ingestion:
  browser_db_paths:
    chrome: "C:/Users/YourName/AppData/Local/Google/Chrome/User Data/Default/History"
    firefox: "C:/Users/YourName/AppData/Roaming/Mozilla/Firefox/Profiles"
```

To find your Chrome History file: open Chrome, go to `chrome://version`, and look at **Profile Path**.

#### Watched directories

List any folders PMS should monitor for new or changed files:

```yaml
ingestion:
  watched_dirs:
    - "C:/Users/YourName/Documents"
    - "C:/Users/YourName/Projects"
  watched_extensions: [".txt", ".md", ".py", ".docx", ".pdf"]
```

Leave `watched_extensions` empty to ingest all file types.

#### AI backend

If you're using Ollama locally (the default), no change is needed. To use a cloud endpoint or a different local model:

```yaml
ai_backend:
  provider: "local"        # or "cloud"
  local:
    base_url: "http://localhost:11434/v1"
    api_key: "ollama"
    model: "qwen2.5:7b"
  cloud:
    base_url: "https://api.openai.com/v1"
    api_key: "sk-..."
    model: "gpt-4o-mini"
```

Switch `provider` to `cloud` to use the cloud settings.

### Changing config at runtime

You can update most settings without restarting the API. In the desktop editor, go to **Settings**, make your changes, and click **Save Settings**. The change is written to `config.yaml` and takes effect immediately for ingestion and search. Changes to the scheduler (consolidation intervals) take effect on the next scheduled run.

---

## 5. Running the API Server

Start the server:

```bat
.venv\Scripts\python.exe run_api.py
```

The API listens on `http://127.0.0.1:8765` by default. You should see log output confirming the database is open, the scheduler is running, and the file watcher has started.

**To use a different config file:**

```bat
set PMS_CONFIG=C:\custom\pms_config.yaml
.venv\Scripts\python.exe run_api.py
```

The API must be running for the desktop editor, the MCP server, and any app integrations to work.

---

## 6. Using the Desktop Editor

Launch the editor:

```bat
.venv\Scripts\python.exe run_editor.py
```

### Connecting to the API

The top bar shows the server URL (default `http://127.0.0.1:8765`) and a **Connect** button. Click Connect — the status indicator turns green when the API is reachable. If the API isn't running, it turns red with a message.

The editor checks the connection every 10 seconds and updates the indicator automatically.

### Dashboard

The Dashboard shows:

- **Memory counts** — current number of STM events, MTM episodes, and LTM concepts
- **Scheduler status** — when STM→MTM and MTM→LTM consolidation last ran
- **Quick Actions** — buttons to manually trigger consolidation at any time
- **Add Memory** — a text box where you can type anything and add it to STM directly

Use **Add Memory** to record something important right now rather than waiting for automatic ingestion.

### Short-Term Memory (STM)

The STM view shows a scrollable list of raw events — everything PMS has ingested recently. Each row shows the time, source (e.g. `chrome`, `file_watcher`, `manual`), keywords, and a snippet of the content.

Use **Delete** to remove a specific event if it was ingested by mistake.

### Mid-Term Memory (MTM)

The MTM view lists AI-generated episode summaries. Each row shows:

- **Time** — when the episode was created
- **Score** — the current importance score (shown as a progress bar). High-scoring episodes are more likely to be promoted to LTM.
- **Tags** — topic tags extracted by the AI
- **Summary** — the episode text

Use **Pin** to lock an important episode so it doesn't decay. Use **Delete** to remove one you don't want kept.

### Long-Term Memory (LTM)

The LTM view lists permanent concept records. Use the **search bar** to run a semantic search — it calls `POST /retrieve` and shows matching concepts by similarity score.

Use **Export** to save a concept as a JSON or plain-text file. Use **Delete** to permanently remove a concept.

### Settings

The Settings view lets you edit `config.yaml` through a form. All sections from the config file are represented — API connection, AI backend, embedding, memory limits, consolidation schedule, and ingestion paths.

Click **Save Settings** to write changes. Click **Refresh** to reload the current saved values.

### Log

The Log view tails `pms_api.log` (or any log file you point it at). Use the **Filter** dropdown to show only INFO, WARNING, ERROR, or DEBUG lines. Toggle **Auto-refresh** to update the view every 2 seconds automatically.

---

## 7. Browser History Ingestion

PMS polls your browser history databases at a configurable interval (default: every 30 minutes). It reads directly from the SQLite files Chrome and Firefox use to store visited URLs, extracts the URL and page title, and ingests each visit as an STM event.

**Important:** PMS makes a temporary copy of the database before reading it, so it never locks your browser's live file.

**Chrome history** is stored in a single SQLite file. PMS reads visits that occurred since the last poll.

**Firefox history** is stored across one or more profile folders. PMS scans all `.sqlite` files in the profiles directory.

To check whether browser ingestion is working, look at the STM view — events with `source: chrome` or `source: firefox` should appear within 30 minutes of browsing.

---

## 8. File Watching

PMS uses the `watchdog` library to monitor directories listed in `watched_dirs`. When a file is created or modified, PMS waits 5 seconds (debounce) to make sure the write is complete, then reads up to the first 2,000 characters of the file and ingests them as an STM event with `source: file_watcher`.

**Tips:**
- Add your notes folder, project directory, or any folder where you save reference material
- Use `watched_extensions` to limit which file types are ingested (empty = all types)
- Very large files are truncated at 2,000 characters — only the beginning is ingested

---

## 9. AI Consolidation

Consolidation is the process that turns raw events into lasting knowledge. It runs automatically on a schedule, but you can also trigger it manually from the Dashboard.

### STM → MTM (every 6 hours, or when STM reaches 80% capacity)

PMS groups recent STM events into batches of 20 and sends each batch to the AI with a prompt asking it to write a concise episode summary, assign an importance score (1–10), and extract topic tags. The resulting episode is stored in MTM.

**What makes a good episode?** The AI is instructed to focus on durable insights — what you were working on, decisions made, things learned — rather than transient details like "opened Gmail."

### MTM → LTM (weekly cron, default Sunday 2am)

PMS sends high-scoring MTM episodes (score ≥ 7, accessed ≥ 2 times) to the AI and asks it to extract permanent facts, preferences, habits, and knowledge. Each extracted concept is embedded into a vector and upserted into LTM. If a very similar concept already exists (cosine similarity ≥ 0.95), the two are merged rather than duplicated.

### Running consolidation manually

Click **Consolidate STM → MTM** or **Consolidate MTM → LTM** on the Dashboard. The button turns orange while running and shows the result when done. This is useful after adding a batch of memories manually or after a long session you want to preserve immediately.

---

## 10. Integrating Other Apps

Any app can read and write PMS memory using plain HTTP. No SDK or special library is required — just an HTTP client.

See **[skill.md](skill.md)** for the complete integration guide with request/response examples and guidance on when to call each operation.

### Recommended pattern for AI assistants

1. At the **start** of a session: call `POST /retrieve` with the current topic to load relevant context
2. During the session: let the AI work normally
3. At the **end** of a session: call `POST /ingest` once with a summary of what was discussed

Calling `ingest` after every single message will flood STM with redundant entries — once per session is the right cadence.

### MCP server

If your AI framework supports MCP, the included stdio server exposes `remember`, `recall`, and `memory_status` as callable tools:

```bat
.venv\Scripts\python.exe run_mcp.py
```

Set `PMS_URL` to override the default API address:

```bat
set PMS_URL=http://127.0.0.1:8765
.venv\Scripts\python.exe run_mcp.py
```

---

## 11. Building a Distributable

To produce standalone executables (no Python installation required on the target machine):

```bat
build.bat
```

This runs PyInstaller twice and then assembles a deployment package:

- `dist/pms_api.exe` — the API server as a single executable
- `dist/pms_editor.exe` — the desktop editor as a single executable
- `dist/deploy/` — a ready-to-deploy folder containing both exes, `config.yaml`, and installer scripts

---

## 12. Installing as a Windows Service

Running PMS as a Windows service means it starts automatically at boot and runs in the background without a visible window.

### Requirements

Download [NSSM (Non-Sucking Service Manager)](https://nssm.cc/download), unzip it, and add the folder to your `PATH`.

### Steps

1. Copy `dist/deploy/` to the target machine (e.g. `C:\PMS\`)
2. Edit `config.yaml` — set your browser paths, watched directories, and AI backend
3. Open a Command Prompt **as Administrator** and run:

```bat
install_service.bat
```

The service installs, starts immediately, and is set to start automatically at every boot. It listens on `http://127.0.0.1:8765`.

4. Launch `pms_editor.exe` and click **Connect** to confirm it's working.

### Viewing service logs

The service writes stdout to `pms_api.log` and stderr to `pms_api_err.log` in the same folder as the exe.

### Uninstalling

Run `uninstall_service.bat` as Administrator.

---

## 13. Configuration Reference

### `api`

| Key | Default | Description |
|---|---|---|
| `host` | `127.0.0.1` | Address the API server binds to. Use `0.0.0.0` to expose on the network. |
| `port` | `8765` | Port number. Change if 8765 is already in use. |

### `storage`

| Key | Default | Description |
|---|---|---|
| `db_path` | `pms.db` | SQLite file for STM and MTM. Created automatically on first run. |
| `ltm_path` | `pms_ltm` | LanceDB directory for LTM vectors. Created automatically. |

### `memory`

| Key | Default | Description |
|---|---|---|
| `stm_capacity` | `500` | Maximum STM events. When full, the oldest event is deleted to make room. |
| `stm_ttl_hours` | `12` | Events older than this are deleted regardless of capacity. |
| `mtm_decay_lambda` | `0.05` | Ebbinghaus decay rate. Higher = faster forgetting. |
| `mtm_score_threshold` | `1.0` | MTM episodes with score below this are deleted during maintenance. |
| `mtm_ttl_days` | `21` | Episodes not accessed for this many days become deletion candidates. |

### `consolidation`

| Key | Default | Description |
|---|---|---|
| `stm_trigger_hours` | `6` | How often STM→MTM consolidation runs automatically. |
| `stm_trigger_pct` | `0.80` | Also triggers consolidation when STM reaches this fraction of capacity. |
| `mtm_schedule` | `0 2 * * 0` | Cron expression for MTM→LTM consolidation (default: Sunday 2am). |

### `embedding`

| Key | Default | Description |
|---|---|---|
| `provider` | `ollama` | Use `ollama` for a local Ollama model, or `sentence_transformers` for a local Python model. |
| `model` | `nomic-embed-text` | Name of the embedding model. |
| `dim` | `768` | Vector dimension. Must match the model output. |
| `ollama_url` | `http://localhost:11434` | Ollama server URL. |

### `ai_backend`

| Key | Default | Description |
|---|---|---|
| `provider` | `local` | `local` uses the `local` block; `cloud` uses the `cloud` block. |
| `local.base_url` | `http://localhost:11434/v1` | OpenAI-compatible chat endpoint. |
| `local.api_key` | `ollama` | API key (Ollama ignores this, but the field is required). |
| `local.model` | `qwen2.5:7b` | Chat model name. |
| `cloud.base_url` | `https://api.openai.com/v1` | Cloud endpoint. |
| `cloud.api_key` | *(empty)* | Your cloud API key. |
| `cloud.model` | `gpt-4o-mini` | Cloud chat model. |

### `ingestion`

| Key | Default | Description |
|---|---|---|
| `browser_db_paths.chrome` | *(Windows default)* | Full path to the Chrome `History` SQLite file. |
| `browser_db_paths.firefox` | *(Windows default)* | Path to the Firefox `Profiles` directory. |
| `browser_poll_interval_min` | `30` | How often (in minutes) to check browser history for new visits. |
| `watched_dirs` | `[]` | List of directories to monitor for file changes. |
| `watched_extensions` | `[]` | File extensions to ingest. Empty list means all extensions. |

---

## 14. REST API Reference

Base URL: `http://127.0.0.1:8765`

### POST `/ingest`

Store a new event in STM.

```json
{ "source": "myapp", "content": "Text to remember.", "metadata": {} }
```

Response: `{ "id": 42, "status": "ok" }`

### POST `/retrieve`

Search across all memory tiers.

```json
{ "query": "search text", "top_k": 10 }
```

Response:
```json
{
  "results": [
    { "id": "42", "content": "...", "score": 0.91, "tier": "stm", "source": "myapp", "timestamp": "..." }
  ],
  "partial": false
}
```

### Memory endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/memory/stm` | List all STM events |
| `DELETE` | `/memory/stm/{id}` | Delete one STM event |
| `GET` | `/memory/mtm` | List MTM episodes (optional `?min_score=`) |
| `PATCH` | `/memory/mtm/{id}` | Update episode — body: `{ "pinned": true }` or `{ "importance_score": 8.5 }` |
| `DELETE` | `/memory/mtm/{id}` | Delete one episode |
| `GET` | `/memory/ltm` | List LTM concepts |
| `DELETE` | `/memory/ltm/{id}` | Delete one concept |

### Admin endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Memory counts and last consolidation times |
| `POST` | `/consolidate/stm` | Manually trigger STM→MTM consolidation |
| `POST` | `/consolidate/mtm` | Manually trigger MTM→LTM consolidation |
| `GET` | `/config` | Return current configuration (API keys redacted) |
| `POST` | `/config` | Update configuration — body: `{ "config": { "memory": { "stm_capacity": 300 } } }` |

---

## 15. Troubleshooting

### The editor shows "Cannot connect"

The API server is not running, or is running on a different port. Start `run_api.py` and check the URL in the editor's top bar matches the `api.host` and `api.port` in `config.yaml`.

### STM events have `source: chrome` but nothing is appearing

Check that `browser_db_paths.chrome` points to the correct file. Open `chrome://version` in Chrome and copy the **Profile Path**, then append `\History`. The path should look like:
`C:\Users\YourName\AppData\Local\Google\Chrome\User Data\Default\History`

### "partial: true" in retrieve results

The embedder (Ollama) is not reachable. Check that Ollama is running (`ollama serve`) and that `nomic-embed-text` is pulled. LTM search is skipped but STM/MTM keyword results are still returned.

### Consolidation runs but produces no MTM episodes

There may not be enough STM events to form a meaningful batch (minimum ~5 events), or the AI returned a response in an unexpected format. Check `pms_api.log` for consolidation output. Make sure `qwen2.5:7b` (or your configured model) is pulled in Ollama.

### The service installed but the API doesn't start

Check `pms_api_err.log` in the deploy folder. Common causes: `config.yaml` has a syntax error, the port is already in use, or the exe path has a space and NSSM wasn't given a quoted path. Re-run `install_service.bat` as Administrator.

### I want to reset everything and start fresh

Stop the service (or API process), delete `pms.db`, `pms.db-shm`, `pms.db-wal`, and the `pms_ltm/` directory, then restart. The database and LTM store are recreated automatically on next start.
