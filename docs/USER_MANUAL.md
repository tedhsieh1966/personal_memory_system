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
6. [Managing the Service](#6-managing-the-service)
7. [Using the Desktop Editor](#7-using-the-desktop-editor)
8. [Browser History Ingestion](#8-browser-history-ingestion)
9. [File Watching](#9-file-watching)
10. [AI Consolidation](#10-ai-consolidation)
11. [Integrating Other Apps](#11-integrating-other-apps)
12. [Building a Distributable](#12-building-a-distributable)
13. [Installing as a Windows Service](#13-installing-as-a-windows-service)
14. [Configuration Reference](#14-configuration-reference)
15. [REST API Reference](#15-rest-api-reference)
16. [Troubleshooting](#16-troubleshooting)

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

### Hardware

The hardware requirements depend almost entirely on whether you run Ollama for local AI. The API, editor, and search engine are lightweight — it's the LLM that sets the bar.

#### Without Ollama (keyword search only)

PMS still ingests, stores, and retrieves memories via BM25 keyword search. This mode is very lightweight:

| Component | Minimum |
|---|---|
| CPU | Any modern dual-core (2015+) |
| RAM | 2 GB free |
| Disk | 500 MB (database + exe) |
| GPU | Not needed |

LTM vector search and AI consolidation are simply skipped. Results are marked `partial: true`.

#### With Ollama — CPU only (no GPU)

Ollama can run `qwen2.5:7b` on CPU using quantised GGUF models. It works, but consolidation is slow — expect 1–3 minutes per batch of 20 events.

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4-core x86-64 (AVX2 support) | 8-core modern CPU |
| RAM | 8 GB | 16 GB |
| Disk | 8 GB free (models + database) | SSD strongly preferred |
| GPU | Not needed | — |

> The two Ollama models together require about 5 GB on disk: `qwen2.5:7b` (~4.7 GB) and `nomic-embed-text` (~274 MB).

#### With Ollama — GPU (recommended for full speed)

A GPU lets Ollama run inference in seconds rather than minutes, making consolidation fast enough to be nearly invisible.

| Component | Minimum | Recommended |
|---|---|---|
| CPU | Any modern quad-core | — |
| RAM | 8 GB | 16 GB |
| VRAM | 6 GB (NVIDIA) | 8 GB+ |
| Disk | 8 GB free | SSD |
| GPU | NVIDIA GTX 1060 6GB | RTX 3060 12 GB or better |

AMD discrete GPUs work with Ollama via ROCm on Linux but have limited Windows support. AMD APU integrated GPUs (e.g. Radeon 780M) can work well on Windows when a large iGPU memory allocation is set in BIOS — with 32 GB+ system RAM, allocating 16 GB to the iGPU lets Ollama treat it as a 16 GB device. On Windows, NVIDIA discrete GPUs remain the most reliable choice.

> If your GPU has less VRAM than the model needs, Ollama automatically offloads layers to CPU RAM. A 4 GB GPU can still accelerate `qwen2.5:7b` partially — it won't be as fast as full GPU inference but is faster than CPU-only.

### Software

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

### Download

Download `pms_installer.exe` from the releases page.

### Before running the installer

**NSSM** (optional, for Windows service): Download from [nssm.cc](https://nssm.cc/download), unzip, and add to your `PATH`. Without NSSM, the installer still copies the application files but cannot install the auto-start service — you can start `pms_server.exe` manually instead.

**Ollama** (optional, for AI features): Download from [ollama.com](https://ollama.com). The installer can pull the required models for you during installation.

### Run the installer

Right-click `pms_installer.exe` and select **Run as administrator** (required for Windows service installation).

The installer window shows three options, all checked by default:

| Option | Effect |
|---|---|
| Create desktop shortcut for PMS Editor | Adds a shortcut to your Desktop |
| Pull Ollama models (qwen2.5:7b, nomic-embed-text) | Downloads the AI and embedding models (~5 GB) |
| Launch editor after install | Opens the editor immediately when done |

Click **Install**. The installer will:

1. Copy `pms_server.exe`, `pms_editor.exe`, `pms_manager.exe`, and `config.yaml` to `%APPDATA%\pms`
2. Install and start the `pms_server` Windows service (set to auto-start at every boot)
3. Pull Ollama models if selected
4. Create a desktop shortcut if selected

If NSSM is not found on `PATH`, a warning is shown — the files are still installed but you must start the API manually (see [Section 5](#5-running-the-api-server)).

### After installation

The API service starts automatically at boot and listens on `http://127.0.0.1:8765`. Open the PMS Editor from your desktop shortcut (or run `pms_editor.exe` from `%APPDATA%\pms`) and click **Connect** to confirm everything is working.

Before first use, edit `config.yaml` in `%APPDATA%\pms` to set your browser paths and watched directories — see [Section 4](#4-configuration).

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
.venv\Scripts\python.exe run_server.py
```

The API listens on `http://127.0.0.1:8765` by default. You should see log output confirming the database is open, the scheduler is running, and the file watcher has started.

**To use a different config file:**

```bat
set PMS_CONFIG=C:\custom\pms_config.yaml
.venv\Scripts\python.exe run_server.py
```

The API must be running for the desktop editor, the MCP server, and any app integrations to work.

---

## 6. Managing the Service

`pms_manager.exe` is a command-line tool for controlling the API service and triggering operations without opening the desktop editor. It is installed to `%APPDATA%\pms` alongside the other executables.

### Commands

`start`, `stop`, and `restart` control the **PMS API Windows service** (`pms_server.exe`) — the background process that handles memory storage, search, browser ingestion, and file watching. They have no effect on Ollama or NSSM. NSSM is not a running daemon; it is only involved at install time as a service wrapper. Ollama runs as its own independent process and has dedicated commands below.

| Command | Description |
|---|---|
| `pms_manager start` | Start the PMS API service |
| `pms_manager stop` | Stop the PMS API service |
| `pms_manager restart` | Restart the PMS API service |
| `pms_manager status` | Show service state, API health, and memory counts |
| `pms_manager consolidate [stm\|mtm]` | Trigger AI consolidation (default: `stm`) |
| `pms_manager log [n]` | Print the last `n` lines of `pms_server.log` (default: 50) |
| `pms_manager ollama-start` | Start Ollama in the background (`ollama serve`) |
| `pms_manager ollama-stop` | Stop the Ollama process |

Commands also accept a `-` or `--` prefix (e.g. `--status`, `-restart`).

### Examples

Check whether the service and API are running:

```bat
pms_manager status
```

Print the last 100 log lines:

```bat
pms_manager log 100
```

Trigger STM→MTM consolidation immediately:

```bat
pms_manager consolidate stm
```

Free up VRAM before gaming or another GPU workload, then restore:

```bat
pms_manager ollama-stop
:: ... do your GPU work ...
pms_manager ollama-start
```

To run `pms_manager` from anywhere, add `%APPDATA%\pms` to your `PATH`, or use the full path:

```bat
"%APPDATA%\pms\pms_manager.exe" status
```

---

## 7. Using the Desktop Editor

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

The Log view tails `pms_server.log` (or any log file you point it at). Use the **Filter** dropdown to show only INFO, WARNING, ERROR, or DEBUG lines. Toggle **Auto-refresh** to update the view every 2 seconds automatically.

---

## 8. Browser History Ingestion

PMS polls your browser history databases at a configurable interval (default: every 30 minutes). It reads directly from the SQLite files Chrome and Firefox use to store visited URLs, extracts the URL and page title, and ingests each visit as an STM event.

**Important:** PMS makes a temporary copy of the database before reading it, so it never locks your browser's live file.

**Chrome history** is stored in a single SQLite file. PMS reads visits that occurred since the last poll.

**Firefox history** is stored across one or more profile folders. PMS scans all `.sqlite` files in the profiles directory.

To check whether browser ingestion is working, look at the STM view — events with `source: chrome` or `source: firefox` should appear within 30 minutes of browsing.

---

## 9. File Watching

PMS uses the `watchdog` library to monitor directories listed in `watched_dirs`. When a file is created or modified, PMS waits 5 seconds (debounce) to make sure the write is complete, then reads up to the first 2,000 characters of the file and ingests them as an STM event with `source: file_watcher`.

**Tips:**
- Add your notes folder, project directory, or any folder where you save reference material
- Use `watched_extensions` to limit which file types are ingested (empty = all types)
- Very large files are truncated at 2,000 characters — only the beginning is ingested

---

## 10. AI Consolidation

Consolidation is the process that turns raw events into lasting knowledge. It runs automatically on a schedule, but you can also trigger it manually from the Dashboard.

### STM → MTM (every 6 hours, or when STM reaches 80% capacity)

PMS groups recent STM events into batches of 20 and sends each batch to the AI with a prompt asking it to write a concise episode summary, assign an importance score (1–10), and extract topic tags. The resulting episode is stored in MTM.

**What makes a good episode?** The AI is instructed to focus on durable insights — what you were working on, decisions made, things learned — rather than transient details like "opened Gmail."

### MTM → LTM (weekly cron, default Sunday 2am)

PMS sends high-scoring MTM episodes (score ≥ 7, accessed ≥ 2 times) to the AI and asks it to extract permanent facts, preferences, habits, and knowledge. Each extracted concept is embedded into a vector and upserted into LTM. If a very similar concept already exists (cosine similarity ≥ 0.95), the two are merged rather than duplicated.

### Running consolidation manually

Click **Consolidate STM → MTM** or **Consolidate MTM → LTM** on the Dashboard. The button turns orange while running and shows the result when done. This is useful after adding a batch of memories manually or after a long session you want to preserve immediately.

---

## 11. Integrating Other Apps

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

## 12. Building a Distributable

To produce standalone executables (no Python installation required on the target machine):

```bat
build.bat
```

This runs PyInstaller twice and then assembles a deployment package:

- `dist/pms_server.exe` — the API server as a single executable
- `dist/pms_editor.exe` — the desktop editor as a single executable
- `dist/deploy/` — a ready-to-deploy folder containing both exes, `config.yaml`, and installer scripts

---

## 13. Installing as a Windows Service

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

The service writes stdout to `pms_server.log` and stderr to `pms_server_err.log` in the same folder as the exe.

### Uninstalling

Run `uninstall_service.bat` as Administrator.

---

## 14. Configuration Reference

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

## 15. REST API Reference

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

## 16. Troubleshooting

### The editor shows "Cannot connect"

The API server is not running, or is running on a different port. Start `run_server.py` and check the URL in the editor's top bar matches the `api.host` and `api.port` in `config.yaml`.

### STM events have `source: chrome` but nothing is appearing

Check that `browser_db_paths.chrome` points to the correct file. Open `chrome://version` in Chrome and copy the **Profile Path**, then append `\History`. The path should look like:
`C:\Users\YourName\AppData\Local\Google\Chrome\User Data\Default\History`

### "partial: true" in retrieve results

The embedder (Ollama) is not reachable. Check that Ollama is running (`ollama serve`) and that `nomic-embed-text` is pulled. LTM search is skipped but STM/MTM keyword results are still returned.

### Consolidation runs but produces no MTM episodes

There may not be enough STM events to form a meaningful batch (minimum ~5 events), or the AI returned a response in an unexpected format. Check `pms_server.log` for consolidation output. Make sure `qwen2.5:7b` (or your configured model) is pulled in Ollama.

### The service installed but the API doesn't start

Check `pms_server_err.log` in the deploy folder. Common causes: `config.yaml` has a syntax error, the port is already in use, or the exe path has a space and NSSM wasn't given a quoted path. Re-run `install_service.bat` as Administrator.

### I want to reset everything and start fresh

Stop the service (or API process), delete `pms.db`, `pms.db-shm`, `pms.db-wal`, and the `pms_ltm/` directory, then restart. The database and LTM store are recreated automatically on next start.

---
---

# PMS 使用手冊

**個人記憶系統 v0.6.0**

本手冊涵蓋從初始設定到日常使用的所有內容。它不僅說明*如何*設定，更解釋*為什麼*系統以這種方式運作。

---

## 目錄

1. [PMS 運作原理](#1-pms-運作原理)
2. [先決條件](#2-先決條件)
3. [安裝](#3-安裝)
4. [設定](#4-設定)
5. [執行 API 伺服器](#5-執行-api-伺服器)
6. [管理服務](#6-管理服務)
7. [使用桌面編輯器](#7-使用桌面編輯器)
8. [瀏覽器歷史紀錄擷取](#8-瀏覽器歷史紀錄擷取)
9. [檔案監控](#9-檔案監控)
10. [AI 整合](#10-ai-整合)
11. [整合其他應用程式](#11-整合其他應用程式)
12. [建置可發佈版本](#12-建置可發佈版本)
13. [安裝為 Windows 服務](#13-安裝為-windows-服務)
14. [設定參考](#14-設定參考)
15. [REST API 參考](#15-rest-api-參考)
16. [疑難排解](#16-疑難排解)

---

## 1. PMS 運作原理

PMS 將您的個人記憶組織成三個層次，各自適合不同的時間範圍。

### 短期記憶（STM）

STM 是一個原始事件的環形緩衝區——您造訪的每個 URL、每個變更的檔案、每段手動輸入的文字。它最多可儲存 500 個事件，預設在 12 小時後過期。可將其視為 RAM：快速、充足，但短暫。

### 中期記憶（MTM）

每隔幾小時，PMS 會請本地 AI 讀取一批 STM 事件並撰寫一個簡潔的*片段*——摘要您在做什麼以及為什麼可能重要。片段在 MTM 中最長保留 21 天，但它們不只是被動地老化：PMS 套用了艾賓浩斯遺忘曲線。您經常回顧的事件會保留；您從未觸碰的事物會逐漸消退。您可以*釘選*重要片段以阻止其衰退。

### 長期記憶（LTM）

每週一次（或按需），PMS 將評分最高的 MTM 片段提煉為持久的*概念*，以向量嵌入方式存儲在 LanceDB 資料庫中。這些概念包括「使用者正在建置一個 Python 記憶系統」或「使用者偏好函數式程式設計風格」。概念無限期保留，並通過語義向量搜尋召回。

### 檢索流程

當您（或應用程式）搜尋某事時，PMS 並行執行兩種搜尋：

- **BM25 關鍵字搜尋**——覆蓋 STM 和 MTM，快速，無需 AI
- **向量相似度搜尋**——覆蓋 LTM，語義化，需要嵌入器

兩者的結果合併、去重，並依相關度分數和新近度的組合重新排名。若嵌入器不可用，PMS 僅返回關鍵字結果（標記為 `partial: true`）。

---

## 2. 先決條件

### 硬體

硬體需求幾乎完全取決於您是否使用 Ollama 進行本地 AI。API、編輯器和搜尋引擎都很輕量——是 LLM 設定了門檻。

#### 不使用 Ollama（僅關鍵字搜尋）

PMS 仍可通過 BM25 關鍵字搜尋擷取、儲存和檢索記憶。此模式非常輕量：

| 元件 | 最低需求 |
|---|---|
| CPU | 任何現代雙核心（2015 年以後） |
| RAM | 2 GB 可用空間 |
| 硬碟 | 500 MB（資料庫 + 執行檔） |
| GPU | 不需要 |

LTM 向量搜尋和 AI 整合將被跳過。結果標記為 `partial: true`。

#### 使用 Ollama——僅 CPU（無 GPU）

Ollama 可以使用量化 GGUF 模型在 CPU 上執行 `qwen2.5:7b`。可以運作，但整合速度較慢——每批 20 個事件預計需要 1–3 分鐘。

| 元件 | 最低需求 | 建議 |
|---|---|---|
| CPU | 4 核心 x86-64（支援 AVX2） | 8 核心現代 CPU |
| RAM | 8 GB | 16 GB |
| 硬碟 | 8 GB 可用空間（模型 + 資料庫） | 強烈建議使用 SSD |
| GPU | 不需要 | — |

> 兩個 Ollama 模型合計約需 5 GB 硬碟空間：`qwen2.5:7b`（約 4.7 GB）和 `nomic-embed-text`（約 274 MB）。

#### 使用 Ollama——GPU（建議以獲得完整速度）

GPU 讓 Ollama 在數秒內完成推論，而非數分鐘，使整合速度快到幾乎無感。

| 元件 | 最低需求 | 建議 |
|---|---|---|
| CPU | 任何現代四核心 | — |
| RAM | 8 GB | 16 GB |
| VRAM | 6 GB（NVIDIA） | 8 GB 以上 |
| 硬碟 | 8 GB 可用空間 | SSD |
| GPU | NVIDIA GTX 1060 6GB | RTX 3060 12 GB 或更好 |

AMD 獨立顯卡可在 Linux 上通過 ROCm 使用 Ollama，Windows 支援有限。AMD APU 整合顯示核心（如 Radeon 780M）在 BIOS 中設定大量 iGPU 記憶體分配後可在 Windows 上良好運作——若系統記憶體 ≥ 32 GB，建議分配 16 GB，Ollama 會將其視為 16 GB 顯示卡。

> 若您的 GPU VRAM 少於模型所需，Ollama 會自動將部分層卸載到 CPU RAM。4 GB GPU 仍可部分加速 `qwen2.5:7b`——不如完整 GPU 推論快，但比純 CPU 更快。

### 軟體

| 需求 | 用途 |
|---|---|
| **Windows 10/11** | 檔案監控和瀏覽器輪詢使用 Windows 特定路徑 |
| **Python 3.11+** | FastAPI 和 LanceDB 的必要條件 |
| **Ollama** | 執行用於 AI 整合的本地 LLM 和用於 LTM 搜尋的嵌入模型 |
| **qwen2.5:7b** | 用於摘要事件和提煉概念的對話模型 |
| **nomic-embed-text** | 用於將文字轉換為 LTM 向量的嵌入模型 |

**Ollama 是可選的。** 若未執行，PMS 會優雅降級：
- STM 和 MTM 仍完全運作（關鍵字搜尋、擷取、瀏覽）
- LTM 搜尋被跳過（結果標記為 `partial: true`）
- AI 整合被跳過，直到 Ollama 可用

從 [ollama.com](https://ollama.com) 安裝 Ollama，然後拉取模型：

```bat
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

## 3. 安裝

### 下載

從發佈頁面下載 `pms_installer.exe`。

### 執行安裝程式前

**NSSM**（可選，用於 Windows 服務）：從 [nssm.cc](https://nssm.cc/download) 下載，解壓縮並加入 `PATH`。若沒有 NSSM，安裝程式仍會複製應用程式檔案，但無法安裝自動啟動服務——您可改為手動啟動 `pms_server.exe`。

**Ollama**（可選，用於 AI 功能）：從 [ollama.com](https://ollama.com) 下載。安裝程式可在安裝過程中自動拉取所需模型。

### 執行安裝程式

右鍵點擊 `pms_installer.exe`，選擇**以系統管理員身份執行**（服務安裝需要系統管理員權限）。

安裝程式視窗顯示三個選項，預設全部勾選：

| 選項 | 效果 |
|---|---|
| 為 PMS 編輯器建立桌面捷徑 | 在桌面新增捷徑 |
| 拉取 Ollama 模型（qwen2.5:7b、nomic-embed-text） | 下載 AI 和嵌入模型（約 5 GB） |
| 安裝完成後啟動編輯器 | 完成後立即開啟編輯器 |

點擊**安裝**。安裝程式將：

1. 將 `pms_server.exe`、`pms_editor.exe`、`pms_manager.exe` 和 `config.yaml` 複製到 `%APPDATA%\pms`
2. 安裝並啟動 `pms_server` Windows 服務（設定為每次開機自動啟動）
3. 若已勾選，拉取 Ollama 模型
4. 若已勾選，建立桌面捷徑

若 `PATH` 中找不到 NSSM，將顯示警告——檔案仍會安裝，但需手動啟動 API（請參閱[第 5 節](#5-執行-api-伺服器)）。

### 安裝完成後

API 服務在開機時自動啟動，並監聽 `http://127.0.0.1:8765`。從桌面捷徑開啟 PMS 編輯器（或從 `%APPDATA%\pms` 執行 `pms_editor.exe`），點擊**連接**以確認一切正常運作。

首次使用前，請編輯 `%APPDATA%\pms` 中的 `config.yaml`，設定您的瀏覽器路徑和監控目錄——請參閱[第 4 節](#4-設定)。

---

## 4. 設定

所有設定都存放在專案根目錄的 `config.yaml` 中。這是人類可讀的 YAML 格式——在啟動 API 前用任何文字編輯器修改即可。

### 最重要的設定項目

#### 瀏覽器路徑

PMS 需要知道您的瀏覽器將歷史紀錄資料庫存放在哪裡。預設值使用 Windows 環境變數（`%LOCALAPPDATA%`、`%APPDATA%`），通常可以正確解析，但若您有非標準的設定檔路徑，請明確指定：

```yaml
ingestion:
  browser_db_paths:
    chrome: "C:/Users/YourName/AppData/Local/Google/Chrome/User Data/Default/History"
    firefox: "C:/Users/YourName/AppData/Roaming/Mozilla/Firefox/Profiles"
```

若要找到您的 Chrome History 檔案：開啟 Chrome，前往 `chrome://version`，查看**設定檔路徑**。

#### 監控目錄

列出 PMS 應監控新增或變更檔案的資料夾：

```yaml
ingestion:
  watched_dirs:
    - "C:/Users/YourName/Documents"
    - "C:/Users/YourName/Projects"
  watched_extensions: [".txt", ".md", ".py", ".docx", ".pdf"]
```

將 `watched_extensions` 留空以擷取所有檔案類型。

#### AI 後端

若您使用本地 Ollama（預設），無需更改。若要使用雲端端點或不同的本地模型：

```yaml
ai_backend:
  provider: "local"        # 或 "cloud"
  local:
    base_url: "http://localhost:11434/v1"
    api_key: "ollama"
    model: "qwen2.5:7b"
  cloud:
    base_url: "https://api.openai.com/v1"
    api_key: "sk-..."
    model: "gpt-4o-mini"
```

將 `provider` 切換為 `cloud` 以使用雲端設定。

### 執行時更改設定

您可以在不重新啟動 API 的情況下更新大多數設定。在桌面編輯器中，前往**設定**，進行更改，然後點擊**儲存設定**。更改將寫入 `config.yaml` 並立即對擷取和搜尋生效。排程器設定（整合間隔）的更改將在下次排程執行時生效。

---

## 5. 執行 API 伺服器

啟動伺服器：

```bat
.venv\Scripts\python.exe run_server.py
```

API 預設監聽 `http://127.0.0.1:8765`。您應看到日誌輸出，確認資料庫已開啟、排程器正在執行以及檔案監控已啟動。

**使用不同的設定檔：**

```bat
set PMS_CONFIG=C:\custom\pms_config.yaml
.venv\Scripts\python.exe run_server.py
```

API 必須在執行中，桌面編輯器、MCP 伺服器和任何應用程式整合才能運作。

---

## 6. 管理服務

`pms_manager.exe` 是一個命令列工具，用於控制 API 服務和觸發操作，無需開啟桌面編輯器。它與其他執行檔一起安裝在 `%APPDATA%\pms`。

### 指令

`start`、`stop` 和 `restart` 控制 **PMS API Windows 服務**（`pms_server.exe`）——負責記憶體儲存、搜尋、瀏覽器擷取和檔案監控的背景程序。這些指令不會影響 Ollama 或 NSSM。NSSM 不是持續運行的程序；它僅在安裝時作為服務包裝器，之後不再介入。Ollama 作為獨立程序運行，有專屬指令如下。

| 指令 | 說明 |
|---|---|
| `pms_manager start` | 啟動 PMS API 服務 |
| `pms_manager stop` | 停止 PMS API 服務 |
| `pms_manager restart` | 重新啟動 PMS API 服務 |
| `pms_manager status` | 顯示服務狀態、API 健康狀況和記憶數量 |
| `pms_manager consolidate [stm\|mtm]` | 觸發 AI 整合（預設：`stm`） |
| `pms_manager log [n]` | 列印 `pms_server.log` 的最後 `n` 行（預設：50） |
| `pms_manager ollama-start` | 在背景啟動 Ollama（`ollama serve`） |
| `pms_manager ollama-stop` | 停止 Ollama 程序 |

指令也接受 `-` 或 `--` 前綴（例如 `--status`、`-restart`）。

### 範例

檢查服務和 API 是否正在執行：

```bat
pms_manager status
```

列印最後 100 行日誌：

```bat
pms_manager log 100
```

立即觸發 STM→MTM 整合：

```bat
pms_manager consolidate stm
```

在遊戲或其他 GPU 工作前釋放顯示記憶體，完成後恢復：

```bat
pms_manager ollama-stop
:: ... 進行 GPU 工作 ...
pms_manager ollama-start
```

若要從任何位置執行 `pms_manager`，請將 `%APPDATA%\pms` 加入 `PATH`，或使用完整路徑：

```bat
"%APPDATA%\pms\pms_manager.exe" status
```

---

## 7. 使用桌面編輯器

開啟編輯器：

```bat
.venv\Scripts\python.exe run_editor.py
```

### 連接到 API

頂部列顯示伺服器 URL（預設 `http://127.0.0.1:8765`）和**連接**按鈕。點擊連接——當 API 可達時，狀態指示燈變為綠色。若 API 未執行，則變為紅色並顯示訊息。

編輯器每 10 秒檢查一次連接並自動更新指示燈。

### 儀表板

儀表板顯示：

- **記憶數量** — STM 事件、MTM 片段和 LTM 概念的當前數量
- **排程器狀態** — STM→MTM 和 MTM→LTM 整合上次執行的時間
- **快速操作** — 隨時手動觸發整合的按鈕
- **新增記憶** — 可以輸入任何內容並直接添加到 STM 的文字框

使用**新增記憶**立即記錄重要事項，而不必等待自動擷取。

### 短期記憶（STM）

STM 視圖顯示原始事件的可捲動列表——PMS 最近擷取的所有內容。每行顯示時間、來源（例如 `chrome`、`file_watcher`、`manual`）、關鍵字和內容摘要。

若事件被誤擷取，使用**刪除**移除特定事件。

### 中期記憶（MTM）

MTM 視圖列出 AI 生成的片段摘要。每行顯示：

- **時間** — 片段建立的時間
- **分數** — 當前重要性分數（顯示為進度條）。高分片段更有可能晉升到 LTM。
- **標籤** — AI 提取的主題標籤
- **摘要** — 片段文字

使用**釘選**鎖定重要片段以防止其衰退。使用**刪除**移除不想保留的片段。

### 長期記憶（LTM）

LTM 視圖列出永久概念記錄。使用**搜尋欄**進行語義搜尋——它呼叫 `POST /retrieve` 並按相似度分數顯示匹配的概念。

使用**匯出**將概念存為 JSON 或純文字檔案。使用**刪除**永久移除概念。

### 設定

設定視圖讓您通過表單編輯 `config.yaml`。設定檔中的所有部分都有對應——API 連接、AI 後端、嵌入、記憶限制、整合排程和擷取路徑。

點擊**儲存設定**以寫入更改。點擊**重新整理**以重新載入當前已儲存的值。

### 日誌

日誌視圖追蹤 `pms_server.log`（或您指定的任何日誌檔案）。使用**篩選**下拉選單僅顯示 INFO、WARNING、ERROR 或 DEBUG 行。切換**自動重新整理**以每 2 秒自動更新視圖。

---

## 8. 瀏覽器歷史紀錄擷取

PMS 以可設定的間隔（預設：每 30 分鐘）輪詢您的瀏覽器歷史紀錄資料庫。它直接從 Chrome 和 Firefox 用於儲存已造訪 URL 的 SQLite 檔案讀取，提取 URL 和頁面標題，並將每次造訪作為 STM 事件擷取。

**重要：** PMS 在讀取前會製作資料庫的臨時副本，因此不會鎖定您瀏覽器的實際檔案。

**Chrome 歷史紀錄**儲存在單一 SQLite 檔案中。PMS 讀取自上次輪詢以來發生的造訪記錄。

**Firefox 歷史紀錄**儲存在一個或多個設定檔資料夾中。PMS 掃描設定檔目錄中的所有 `.sqlite` 檔案。

若要檢查瀏覽器擷取是否正常運作，請查看 STM 視圖——帶有 `source: chrome` 或 `source: firefox` 的事件應在瀏覽後 30 分鐘內出現。

---

## 9. 檔案監控

PMS 使用 `watchdog` 程式庫監控 `watched_dirs` 中列出的目錄。當檔案被建立或修改時，PMS 等待 5 秒（防抖）以確保寫入完成，然後讀取最多 2,000 個字元並將其作為帶有 `source: file_watcher` 標記的 STM 事件擷取。

**提示：**
- 添加您的筆記資料夾、專案目錄或任何儲存參考資料的資料夾
- 使用 `watched_extensions` 限制擷取的檔案類型（空白 = 所有類型）
- 非常大的檔案會在 2,000 個字元處截斷——只有開頭部分會被擷取

---

## 10. AI 整合

整合是將原始事件轉變為持久知識的過程。它按排程自動執行，但您也可以從儀表板手動觸發。

### STM → MTM（每 6 小時，或 STM 達到 80% 容量時）

PMS 將最近的 STM 事件分成每批 20 個，並將每批發送給 AI，請求其撰寫簡潔的片段摘要、分配重要性分數（1–10）並提取主題標籤。生成的片段儲存在 MTM 中。

**什麼是好的片段？** AI 被指示專注於持久的洞察——您在做什麼、做出的決策、學到的東西——而非「打開了 Gmail」等短暫細節。

### MTM → LTM（每週排程，預設週日凌晨 2 點）

PMS 將高分的 MTM 片段（分數 ≥ 7，存取次數 ≥ 2）發送給 AI，請求提取永久事實、偏好、習慣和知識。每個提取的概念被嵌入為向量並插入或更新 LTM。若已存在非常相似的概念（餘弦相似度 ≥ 0.95），兩者會合併而非重複。

### 手動執行整合

在儀表板上點擊**整合 STM → MTM** 或**整合 MTM → LTM**。執行時按鈕變橙色，完成後顯示結果。這在手動添加大量記憶或完成長時間工作階段後特別有用。

---

## 11. 整合其他應用程式

任何應用程式都可以使用純 HTTP 讀寫 PMS 記憶。不需要 SDK 或特殊程式庫——只需一個 HTTP 客戶端。

請參閱 **[skill.md](skill.md)** 以取得包含請求/回應範例和各操作呼叫時機指引的完整整合指南。

### AI 助理的建議模式

1. 在工作階段**開始**時：呼叫 `POST /retrieve` 加載相關上下文
2. 工作階段**期間**：讓 AI 正常工作
3. 在工作階段**結束**時：呼叫一次 `POST /ingest`，附上對話摘要

在每條訊息後呼叫 `ingest` 會以冗餘條目充斥 STM——每個工作階段一次是正確的頻率。

### MCP 伺服器

若您的 AI 框架支援 MCP，附帶的 stdio 伺服器將 `remember`、`recall` 和 `memory_status` 公開為可呼叫的工具：

```bat
.venv\Scripts\python.exe run_mcp.py
```

設定 `PMS_URL` 以覆蓋預設 API 位址：

```bat
set PMS_URL=http://127.0.0.1:8765
.venv\Scripts\python.exe run_mcp.py
```

---

## 12. 建置可發佈版本

要生成獨立執行檔（目標機器不需要安裝 Python）：

```bat
build.bat
```

這會執行 PyInstaller 兩次，然後組裝部署套件：

- `dist/pms_server.exe` — 作為單一執行檔的 API 伺服器
- `dist/pms_editor.exe` — 作為單一執行檔的桌面編輯器
- `dist/deploy/` — 一個包含兩個執行檔、`config.yaml` 和安裝腳本的即時部署資料夾

---

## 13. 安裝為 Windows 服務

將 PMS 作為 Windows 服務執行意味著它在開機時自動啟動，在背景中運行而不顯示視窗。

### 需求

下載 [NSSM（Non-Sucking Service Manager）](https://nssm.cc/download)，解壓縮，並將資料夾加入您的 `PATH`。

### 步驟

1. 將 `dist/deploy/` 複製到目標機器（例如 `C:\PMS\`）
2. 編輯 `config.yaml`——設定您的瀏覽器路徑、監控目錄和 AI 後端
3. 以**系統管理員身份**開啟命令提示字元並執行：

```bat
install_service.bat
```

服務安裝完成後立即啟動，並設定為每次開機自動啟動。它監聽 `http://127.0.0.1:8765`。

4. 開啟 `pms_editor.exe` 並點擊**連接**以確認其正常運作。

### 查看服務日誌

服務將標準輸出寫入執行檔所在資料夾中的 `pms_server.log`，將標準錯誤寫入 `pms_server_err.log`。

### 解除安裝

以系統管理員身份執行 `uninstall_service.bat`。

---

## 14. 設定參考

### `api`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `host` | `127.0.0.1` | API 伺服器綁定的位址。使用 `0.0.0.0` 在網路上公開。 |
| `port` | `8765` | 連接埠號碼。若 8765 已被使用，請更改。 |

### `storage`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `db_path` | `pms.db` | STM 和 MTM 的 SQLite 檔案。第一次執行時自動建立。 |
| `ltm_path` | `pms_ltm` | LTM 向量的 LanceDB 目錄。自動建立。 |

### `memory`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `stm_capacity` | `500` | 最大 STM 事件數。達到上限時，最舊的事件會被刪除以騰出空間。 |
| `stm_ttl_hours` | `12` | 超過此時間的事件無論容量如何都會被刪除。 |
| `mtm_decay_lambda` | `0.05` | 艾賓浩斯衰退率。越高 = 遺忘越快。 |
| `mtm_score_threshold` | `1.0` | MTM 片段分數低於此值時，在維護期間被刪除。 |
| `mtm_ttl_days` | `21` | 超過此天數未被存取的片段成為刪除候選。 |

### `consolidation`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `stm_trigger_hours` | `6` | STM→MTM 整合自動執行的頻率（小時）。 |
| `stm_trigger_pct` | `0.80` | 當 STM 達到此容量比例時也會觸發整合。 |
| `mtm_schedule` | `0 2 * * 0` | MTM→LTM 整合的 Cron 表達式（預設：週日凌晨 2 點）。 |

### `embedding`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `provider` | `ollama` | 使用 `ollama` 表示本地 Ollama 模型，`sentence_transformers` 表示本地 Python 模型。 |
| `model` | `nomic-embed-text` | 嵌入模型名稱。 |
| `dim` | `768` | 向量維度。必須與模型輸出匹配。 |
| `ollama_url` | `http://localhost:11434` | Ollama 伺服器 URL。 |

### `ai_backend`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `provider` | `local` | `local` 使用 `local` 區塊；`cloud` 使用 `cloud` 區塊。 |
| `local.base_url` | `http://localhost:11434/v1` | OpenAI 相容的對話端點。 |
| `local.api_key` | `ollama` | API 金鑰（Ollama 忽略此項，但欄位為必填）。 |
| `local.model` | `qwen2.5:7b` | 對話模型名稱。 |
| `cloud.base_url` | `https://api.openai.com/v1` | 雲端端點。 |
| `cloud.api_key` | *（空）* | 您的雲端 API 金鑰。 |
| `cloud.model` | `gpt-4o-mini` | 雲端對話模型。 |

### `ingestion`

| 鍵 | 預設值 | 說明 |
|---|---|---|
| `browser_db_paths.chrome` | *（Windows 預設）* | Chrome `History` SQLite 檔案的完整路徑。 |
| `browser_db_paths.firefox` | *（Windows 預設）* | Firefox `Profiles` 目錄的路徑。 |
| `browser_poll_interval_min` | `30` | 檢查瀏覽器歷史紀錄新造訪記錄的頻率（分鐘）。 |
| `watched_dirs` | `[]` | 要監控檔案變更的目錄列表。 |
| `watched_extensions` | `[]` | 要擷取的副檔名。空列表表示所有副檔名。 |

---

## 15. REST API 參考

基礎 URL：`http://127.0.0.1:8765`

### POST `/ingest`

在 STM 中儲存新事件。

```json
{ "source": "myapp", "content": "要記住的文字。", "metadata": {} }
```

回應：`{ "id": 42, "status": "ok" }`

### POST `/retrieve`

跨所有記憶層搜尋。

```json
{ "query": "搜尋文字", "top_k": 10 }
```

回應：
```json
{
  "results": [
    { "id": "42", "content": "...", "score": 0.91, "tier": "stm", "source": "myapp", "timestamp": "..." }
  ],
  "partial": false
}
```

### 記憶端點

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/memory/stm` | 列出所有 STM 事件 |
| `DELETE` | `/memory/stm/{id}` | 刪除一個 STM 事件 |
| `GET` | `/memory/mtm` | 列出 MTM 片段（可選 `?min_score=`） |
| `PATCH` | `/memory/mtm/{id}` | 更新片段——本體：`{ "pinned": true }` 或 `{ "importance_score": 8.5 }` |
| `DELETE` | `/memory/mtm/{id}` | 刪除一個片段 |
| `GET` | `/memory/ltm` | 列出 LTM 概念 |
| `DELETE` | `/memory/ltm/{id}` | 刪除一個概念 |

### 管理端點

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/status` | 記憶數量和最後整合時間 |
| `POST` | `/consolidate/stm` | 手動觸發 STM→MTM 整合 |
| `POST` | `/consolidate/mtm` | 手動觸發 MTM→LTM 整合 |
| `GET` | `/config` | 返回當前設定（API 金鑰已遮蔽） |
| `POST` | `/config` | 更新設定——本體：`{ "config": { "memory": { "stm_capacity": 300 } } }` |

---

## 16. 疑難排解

### 編輯器顯示「無法連接」

API 伺服器未執行，或在不同的連接埠上執行。啟動 `run_server.py` 並檢查編輯器頂部列中的 URL 是否與 `config.yaml` 中的 `api.host` 和 `api.port` 匹配。

### STM 事件有 `source: chrome` 但沒有出現任何內容

檢查 `browser_db_paths.chrome` 是否指向正確的檔案。在 Chrome 中開啟 `chrome://version` 並複製**設定檔路徑**，然後加上 `\History`。路徑應如下所示：
`C:\Users\YourName\AppData\Local\Google\Chrome\User Data\Default\History`

### 檢索結果中有「partial: true」

嵌入器（Ollama）無法連接。檢查 Ollama 是否正在執行（`ollama serve`）以及 `nomic-embed-text` 是否已拉取。LTM 搜尋被跳過，但 STM/MTM 關鍵字結果仍會返回。

### 整合執行但沒有產生 MTM 片段

可能沒有足夠的 STM 事件形成有意義的批次（最少約 5 個事件），或 AI 以意外格式返回回應。查看 `pms_server.log` 中的整合輸出。確保 Ollama 中已拉取 `qwen2.5:7b`（或您設定的模型）。

### 服務已安裝但 API 未啟動

查看部署資料夾中的 `pms_server_err.log`。常見原因：`config.yaml` 有語法錯誤、連接埠已被使用，或執行檔路徑含有空格而 NSSM 未給出帶引號的路徑。以系統管理員身份重新執行 `install_service.bat`。

### 我想重置所有內容並重新開始

停止服務（或 API 程序），刪除 `pms.db`、`pms.db-shm`、`pms.db-wal` 和 `pms_ltm/` 目錄，然後重新啟動。資料庫和 LTM 儲存區在下次啟動時會自動重建。
