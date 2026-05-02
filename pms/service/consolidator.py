from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from .config import get_config
from .db import get_conn
from . import embedder
from . import ltm as ltm_svc
from . import mtm as mtm_svc
from . import stm as stm_svc

logger = logging.getLogger(__name__)

_STM_BATCH_SIZE = 20

_STM_SYSTEM = (
    "You are a personal memory consolidation assistant. Your job is to summarise "
    "a batch of raw activity events into a concise episode record."
)

_MTM_SYSTEM = (
    "You are a personal knowledge distillation assistant. Extract durable facts, "
    "preferences, habits, and knowledge from episode summaries."
)


# ── AI client ────────────────────────────────────────────────────────────────

def _ai_client():
    import openai
    cfg = get_config()["ai_backend"]
    backend = cfg[cfg["provider"]]
    return openai.OpenAI(
        base_url=backend["base_url"],
        api_key=backend["api_key"],
        timeout=60.0,
    )


def _model() -> str:
    cfg = get_config()["ai_backend"]
    return cfg[cfg["provider"]]["model"]


def _chat(system: str, user: str) -> str | None:
    try:
        resp = _ai_client().chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("AI call failed: %s", exc)
        return None


# ── STM → MTM ────────────────────────────────────────────────────────────────

def run_stm_to_mtm() -> dict:
    """Batch-consolidate STM events older than stm_trigger_hours into MTM episodes."""
    cfg = get_config()
    cutoff = time.time() - cfg["consolidation"]["stm_trigger_hours"] * 3600

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM stm_events WHERE created_at < ? ORDER BY source, created_at ASC",
        (cutoff,),
    ).fetchall()

    if not rows:
        return {"batches_processed": 0, "events_consolidated": 0}

    batches = [rows[i : i + _STM_BATCH_SIZE] for i in range(0, len(rows), _STM_BATCH_SIZE)]
    consolidated = 0
    batches_ok = 0

    for batch in batches:
        ep_id = _consolidate_stm_batch(batch)
        if ep_id is not None:
            ids = [dict(r)["id"] for r in batch]
            ph = ",".join("?" * len(ids))
            with conn:
                conn.execute(f"DELETE FROM stm_events WHERE id IN ({ph})", ids)
            consolidated += len(batch)
            batches_ok += 1

    return {"batches_processed": batches_ok, "events_consolidated": consolidated}


def _consolidate_stm_batch(rows) -> int | None:
    events = [
        {
            "source": dict(r)["source"],
            "content": dict(r)["content"],
            "timestamp": datetime.fromtimestamp(dict(r)["created_at"], tz=timezone.utc).isoformat(),
        }
        for r in rows
    ]
    t0 = datetime.fromtimestamp(dict(rows[0])["created_at"], tz=timezone.utc).isoformat()
    t1 = datetime.fromtimestamp(dict(rows[-1])["created_at"], tz=timezone.utc).isoformat()

    user_msg = (
        f"Below are {len(rows)} activity events captured between {t0} and {t1}.\n"
        "Summarise them into an episode record with the following JSON structure:\n\n"
        '{\n'
        '  "summary": "<3-5 sentence narrative summary of what the user was doing>",\n'
        '  "topic_tags": ["<tag1>", "<tag2>", ...],\n'
        '  "importance_score": <integer 1-10>\n'
        '}\n\n'
        "Scoring guide: 10 = highly significant (major decision, important document); "
        "1 = trivial (background browsing, routine task).\n\n"
        f"Events:\n{json.dumps(events, indent=2)}\n\n"
        "Respond with ONLY the JSON object. No markdown, no explanation."
    )

    raw = _chat(_STM_SYSTEM, user_msg)
    if raw is None:
        return None

    try:
        parsed = json.loads(raw)
        summary: str = parsed["summary"]
        tags: list[str] = parsed.get("topic_tags", [])
        score = float(max(1, min(10, parsed.get("importance_score", 5))))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("STM→MTM JSON parse failed: %s | raw: %.200s", exc, raw)
        return None

    source_ids = [dict(r)["id"] for r in rows]
    return mtm_svc.insert(summary, tags, score, source_ids)


# ── MTM → LTM ────────────────────────────────────────────────────────────────

def run_mtm_to_ltm() -> dict:
    """Distil eligible MTM episodes (score≥7, access≥2) into LTM concepts."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM mtm_episodes "
        "WHERE importance_score >= 7 AND access_count >= 2 "
        "ORDER BY created_at DESC",
    ).fetchall()

    if not rows:
        return {"episodes_processed": 0, "concepts_created": 0}

    episodes = []
    for r in rows:
        d = dict(r)
        episodes.append({
            "summary": d["summary"],
            "topic_tags": json.loads(d["topic_tags"] or "[]"),
            "importance_score": d["importance_score"],
            "created_at": datetime.fromtimestamp(d["created_at"], tz=timezone.utc).isoformat(),
        })

    oldest_ts = dict(rows[-1])["created_at"]
    days = max(1, int((time.time() - oldest_ts) / 86400))
    period = f"{days} day{'s' if days != 1 else ''}"

    user_msg = (
        f"Below are {len(rows)} episode summaries from the past {period}.\n"
        "Extract a list of durable personal knowledge statements — things that are "
        "likely to remain true beyond today.\n\n"
        "Return a JSON array of strings:\n"
        '["<statement 1>", "<statement 2>", ...]\n\n'
        "Rules:\n"
        '- Each statement is a single clear sentence.\n'
        '- Do NOT include time-bound events ("user attended a meeting on Tuesday").\n'
        "- DO include preferences, skills, recurring patterns, important facts.\n"
        "- Maximum 20 statements.\n\n"
        f"Episodes:\n{json.dumps(episodes, indent=2)}\n\n"
        "Respond with ONLY the JSON array. No markdown, no explanation."
    )

    raw = _chat(_MTM_SYSTEM, user_msg)
    if raw is None:
        return {"episodes_processed": 0, "concepts_created": 0}

    try:
        concepts = json.loads(raw)
        if not isinstance(concepts, list):
            raise ValueError("expected list")
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("MTM→LTM JSON parse failed: %s | raw: %.200s", exc, raw)
        return {"episodes_processed": 0, "concepts_created": 0}

    ep_ids = [str(dict(r)["id"]) for r in rows]
    created = 0
    for concept in concepts[:20]:
        if not isinstance(concept, str) or not concept.strip():
            continue
        vec = embedder.embed(concept.strip())
        if vec is None:
            logger.warning("Embedding unavailable; skipping concept: %.60s", concept)
            continue
        ltm_svc.upsert_concept(concept.strip(), vec, ep_ids)
        created += 1

    return {"episodes_processed": len(rows), "concepts_created": created}


# ── Maintenance ──────────────────────────────────────────────────────────────

def run_maintenance() -> dict:
    """Hourly: delete expired STM events and apply Ebbinghaus decay to MTM."""
    stm_deleted = stm_svc.delete_expired()
    mtm_updated = mtm_svc.apply_decay()
    return {"stm_deleted": stm_deleted, "mtm_updated": mtm_updated}
