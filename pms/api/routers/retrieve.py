from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..models import RankedMemory, RetrieveResponse
from ..services import embedder
from ..services import ltm as ltm_svc
from ..services import mtm as mtm_svc
from ..services import stm as stm_svc

router = APIRouter(prefix="/retrieve", tags=["retrieve"])

_EMBED_TIMEOUT = 1.5  # seconds; fall back to BM25-only if exceeded


@router.get("", response_model=RetrieveResponse)
async def retrieve(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=100),
) -> RetrieveResponse:
    # ── BM25 (STM + MTM) ───────────────────────────────────────────────────
    stm_hits, mtm_hits = await asyncio.gather(
        asyncio.to_thread(stm_svc.bm25_search, q, top_k * 2),
        asyncio.to_thread(mtm_svc.bm25_search, q, top_k * 2),
    )

    # ── Vector search (LTM) ────────────────────────────────────────────────
    ltm_hits: list[dict] = []
    partial = False

    if embedder.is_available():
        try:
            query_vector = await asyncio.wait_for(
                asyncio.to_thread(embedder.embed, q),
                timeout=_EMBED_TIMEOUT,
            )
            if query_vector:
                ltm_hits = await asyncio.to_thread(
                    ltm_svc.vector_search, query_vector, top_k * 2
                )
        except asyncio.TimeoutError:
            partial = True
        except Exception:
            partial = True
    else:
        partial = ltm_svc.count() > 0  # partial only if there's LTM data we couldn't search

    # ── Score & merge ───────────────────────────────────────────────────────
    now = time.time()
    candidates: list[RankedMemory] = []

    # Normalise BM25 ranks → [0, 1]  (FTS5 rank is negative; more negative = better)
    bm25_hits = [(h, "stm") for h in stm_hits] + [(h, "mtm") for h in mtm_hits]
    if bm25_hits:
        ranks = [h[0].get("rank", 0.0) for h in bm25_hits]
        r_min, r_max = min(ranks), max(ranks)
        r_range = r_min - r_max  # negative

        def norm_bm25(r: float) -> float:
            return 1.0 if r_range == 0 else (r - r_max) / r_range

        for hit, tier in bm25_hits:
            raw = norm_bm25(hit.get("rank", r_max))
            age_h = (now - hit["created_at"]) / 3600
            score = raw * math.exp(-0.01 * age_h)
            content = hit["content"] if tier == "stm" else hit["summary"]
            source = hit["source"] if tier == "stm" else "consolidation"
            candidates.append(RankedMemory(
                tier=tier,  # type: ignore[arg-type]
                id=hit["id"],
                content=content,
                score=score,
                source=source,
                timestamp=datetime.fromtimestamp(hit["created_at"], tz=timezone.utc),
            ))

    # LTM: cosine similarity = 1 - _distance (already in [0, 1])
    for hit in ltm_hits:
        sim = max(0.0, 1.0 - float(hit.get("_distance", 1.0)))
        age_h = (now - float(hit["created_at"])) / 3600
        score = sim * math.exp(-0.01 * age_h)
        candidates.append(RankedMemory(
            tier="ltm",
            id=hit["id"],
            content=hit["concept"],
            score=score,
            source="ltm",
            timestamp=datetime.fromtimestamp(float(hit["created_at"]), tz=timezone.utc),
        ))

    candidates.sort(key=lambda x: x.score, reverse=True)
    return RetrieveResponse(results=candidates[:top_k], partial=partial)
