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
- **Multilingual UI** — Editor and installer display in English, 繁體中文, or 簡体中文; language auto-detected from the system input method
- **REST API + Skill** — Any app or AI can call `POST /ingest` and `POST /retrieve` — see [docs/skill.md](docs/skill.md)
- **Windows service** — Installed and started by `pms_installer.exe`; auto-starts at every boot via NSSM (bundled)

---

## Screenshots

> *Coming soon — editor screenshots and demo GIF*

---

## Quick Start

**Prerequisites:** Windows 10/11 · Python 3.11+ · 8 GB RAM (16 GB recommended) · [Ollama](https://ollama.com) optional but recommended for AI consolidation · NVIDIA GPU with 6 GB+ VRAM, or AMD GPU (discrete with ROCm, or AMD APU iGPU with large system RAM allocated in BIOS), for fast local inference

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
.venv\Scripts\python.exe run_server.py
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

See [docs/skill.md](docs/skill.md) for the full integration guide including request/response shapes, examples, and caller guidance for AI assistants.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | Full setup guide, editor walkthrough, configuration explained, troubleshooting |
| [docs/skill.md](docs/skill.md) | API integration descriptor for apps and AI assistants |
| [config.yaml](config.yaml) | Annotated default configuration |

---

## Project Structure

```
PersonalMemory/
├── pms/
│   ├── service/      # Pure logic: STM/MTM/LTM, consolidation, ingestion
│   ├── server/       # FastAPI HTTP layer
│   ├── editor/       # CustomTkinter desktop GUI
│   └── mcp/          # MCP stdio server
├── tests/            # 110 tests, no Ollama required
├── docs/skill.md          # Integration descriptor
├── docs/USER_MANUAL.md    # Full user manual
├── run_server.py        # Start the API server
├── run_editor.py     # Launch the desktop editor
├── run_mcp.py        # Start the MCP server
├── build.bat         # Build distributable exes + deploy package
└── config.yaml       # Configuration
```

---

## License

Private / personal use.
**Author:** Ted Hsieh &lt;ted1966@gmail.com&gt;

---
---

# 個人記憶系統（PMS）

**您的個人 AI 記憶——完全在您自己的電腦上運行。**

PMS 靜靜地從您閱讀、撰寫和談論的內容中學習。隨時詢問，它就能呈現正確的上下文——無論是今早的瀏覽分頁還是上個月的筆記。無雲端。無訂閱。資料不會離開您的電腦。

---

## 為什麼選擇 PMS？

大多數 AI 助理在您關閉對話後就會忘記一切。PMS 為任何 AI——或您自己的應用程式——提供持久、可搜尋的記憶，並隨時間變得更聰明。

- **SmartPal 上週二有過對話？** PMS 記得。
- **三週前讀過一篇關於 Rust 的文章？** PMS 可以找到它。
- **您的 AI 助理在回答前需要上下文？** 它呼叫 `recall`，一切盡知。

---

## 主要功能

- **三層記憶** — 短期（數小時）→ 中期（數週）→ 長期（永久概念），各層自動晉升
- **AI 整合** — 原始事件被摘要為片段；片段使用本地 LLM（Ollama / 任何 OpenAI 相容端點）提煉為持久概念
- **艾賓浩斯遺忘曲線** — 中期記憶若未存取則自然衰退；已釘選的片段會被保留
- **混合搜尋** — BM25 關鍵字搜尋 + 向量相似度搜尋，依新近度組合排名
- **瀏覽器擷取** — 在背景自動索引 Chrome 和 Firefox 歷史紀錄
- **檔案監控** — 監控目錄中的新增/變更文件並進行擷取
- **桌面編輯器** — 完整的 CustomTkinter GUI，可瀏覽、搜尋、釘選、刪除和匯出記憶
- **多語系 UI** — 編輯器與安裝程式支援 English、繁體中文、簡体中文；自動偵測系統輸入法語言
- **REST API + 技能** — 任何應用程式或 AI 均可呼叫 `POST /ingest` 和 `POST /retrieve`——請參閱 [docs/skill.md](docs/skill.md)
- **Windows 服務** — 由 `pms_installer.exe` 安裝並啟動；每次開機自動執行（使用內建 NSSM）

---

## 螢幕截圖

> *即將推出——編輯器截圖和示範 GIF*

---

## 快速開始

**先決條件：** Windows 10/11 · Python 3.11+ · 8 GB RAM（建議 16 GB）· [Ollama](https://ollama.com) 可選但建議用於 AI 整合 · 具有 6 GB+ VRAM 的 NVIDIA GPU，或支援 ROCm 的 AMD 獨立顯卡，或搭配大容量系統記憶體並在 BIOS 中分配 iGPU 記憶體的 AMD APU，以實現快速本地推論

```bat
git clone <repo>
cd PersonalMemory
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

啟動 API：
```bat
.venv\Scripts\python.exe run_server.py
```

開啟編輯器：
```bat
.venv\Scripts\python.exe run_editor.py
```

> 沒有 Ollama 也能使用 PMS——檢索會回退至關鍵字搜尋，AI 整合將暫停直到模型可用。

---

## 與其他應用程式整合

任何應用程式或 AI 都可以透過兩個 HTTP 呼叫使用 PMS 記憶：

```python
import httpx

# 儲存記憶
httpx.post("http://127.0.0.1:8765/ingest", json={
    "source": "myapp",
    "content": "User prefers dark mode and short meetings."
})

# 搜尋記憶
results = httpx.post("http://127.0.0.1:8765/retrieve", json={
    "query": "user preferences"
}).json()
```

請參閱 [docs/skill.md](docs/skill.md) 以取得完整整合指南，包含請求/回應格式、範例及 AI 助理呼叫指引。

---

## 說明文件

| 文件 | 內容 |
|---|---|
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | 完整設定指南、編輯器使用說明、設定說明、疑難排解 |
| [docs/skill.md](docs/skill.md) | 應用程式和 AI 助理的 API 整合描述符 |
| [config.yaml](config.yaml) | 附註解的預設設定 |

---

## 專案結構

```
PersonalMemory/
├── pms/
│   ├── service/      # 純邏輯：STM/MTM/LTM、整合、擷取
│   ├── server/       # FastAPI HTTP 層
│   ├── editor/       # CustomTkinter 桌面 GUI
│   └── mcp/          # MCP stdio 伺服器
├── tests/            # 110 個測試，不需要 Ollama
├── docs/skill.md          # 整合描述符
├── docs/USER_MANUAL.md    # 完整使用手冊
├── run_server.py        # 啟動 API 伺服器
├── run_editor.py     # 開啟桌面編輯器
├── run_mcp.py        # 啟動 MCP 伺服器
├── build.bat         # 建置可發佈執行檔 + 部署套件
└── config.yaml       # 設定檔
```

---

## 授權

私人／個人使用。
**作者：** Ted Hsieh &lt;ted1966@gmail.com&gt;
