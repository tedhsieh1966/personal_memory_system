# Skill: Personal Memory System (PMS)

A local, privacy-first memory service for Windows. Stores, consolidates, and retrieves personal memories across three tiers (short-term, mid-term, long-term). All data stays on the user's machine.

## Prerequisites

- PMS API must be running locally (default: `http://127.0.0.1:8765`)
- Override the base URL via the `PMS_URL` environment variable

---

## Operations

### 1. Remember — store a memory

Save something worth remembering. Content lands in short-term memory and is automatically consolidated into long-term memory over time.

**Request**
```
POST {PMS_URL}/ingest
Content-Type: application/json

{
  "content":  "<text to remember>",
  "source":   "<caller name, e.g. smartpal | claude | manual>",
  "metadata": { "<key>": "<value>" }   // optional
}
```

**Response**
```json
{ "id": 42, "status": "ok" }
```

**Example**
```json
POST /ingest
{
  "content": "User prefers dark mode and dislikes long meetings.",
  "source": "smartpal",
  "metadata": { "session": "2026-04-25-morning" }
}
```

---

### 2. Recall — search memories

Hybrid BM25 + vector search across all memory tiers. Returns results ranked by relevance and recency.

**Request**
```
POST {PMS_URL}/retrieve
Content-Type: application/json

{
  "query": "<search text>",
  "top_k": 10              // optional, default 10
}
```

**Response**
```json
{
  "results": [
    {
      "id":         "42",
      "content":    "User prefers dark mode and dislikes long meetings.",
      "score":      0.91,
      "tier":       "stm",
      "source":     "smartpal",
      "timestamp":  "2026-04-25T09:12:00"
    }
  ],
  "partial": false
}
```

`partial: true` means long-term memory was not searched (embedder unavailable).

**Tiers:** `stm` (last 12 h) · `mtm` (last 21 days) · `ltm` (permanent concepts)

**Example**
```json
POST /retrieve
{ "query": "user preferences UI", "top_k": 5 }
```

---

### 3. Memory Status — check the service

Returns memory counts and last consolidation timestamps.

**Request**
```
GET {PMS_URL}/status
```

**Response**
```json
{
  "stm_count":               14,
  "mtm_count":                3,
  "ltm_count":                7,
  "scheduler_running":      true,
  "last_stm_consolidation": "2026-04-25T06:00:00",
  "last_mtm_consolidation": "2026-04-20T02:00:00",
  "last_maintenance":       "2026-04-25T07:00:00"
}
```

---

## When to use each operation

| Situation | Operation |
|---|---|
| End of a conversation — save what matters | `remember` |
| User asks "do you remember…" | `recall` |
| Before answering — check for relevant context | `recall` |
| Verify memory service is up | `memory_status` |
| Periodic session summary | `remember` (one call per session) |

## Caller guidance

- Call `recall` **before** answering questions about the user's history, preferences, or past work — the answer may already be in memory.
- Call `remember` **once per session** at the end (not after every message) to avoid flooding short-term memory with redundant entries.
- Use a descriptive `source` (e.g. `"smartpal"`) so memories from different callers are distinguishable.
- `metadata` is free-form — include whatever context helps (session ID, app version, topic tags).
