from __future__ import annotations

from .config import get_config

_st_model = None


def embed(text: str) -> list[float] | None:
    """Embed text using the provider configured in config.yaml. Returns None on failure."""
    cfg = get_config()
    emb = cfg["embedding"]
    provider: str = emb["provider"]

    if provider == "ollama":
        return _embed_ollama(text, emb["model"], emb["ollama_url"])
    if provider == "sentence_transformers":
        return _embed_sentence_transformers(text, emb["model"])
    return None


def is_available() -> bool:
    """Quick liveness check for the configured embedding provider."""
    try:
        cfg = get_config()
        provider: str = cfg["embedding"]["provider"]
        if provider == "ollama":
            import httpx
            resp = httpx.get(
                f"{cfg['embedding']['ollama_url']}/api/tags", timeout=2.0
            )
            return resp.status_code == 200
        if provider == "sentence_transformers":
            import sentence_transformers  # noqa: F401
            return True
    except Exception:
        pass
    return False


def _embed_ollama(text: str, model: str, base_url: str) -> list[float] | None:
    try:
        import httpx
        resp = httpx.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception:
        return None


def _embed_sentence_transformers(text: str, model_name: str) -> list[float] | None:
    global _st_model
    try:
        if _st_model is None:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer(model_name)
        return _st_model.encode(text, show_progress_bar=False).tolist()
    except Exception:
        return None
