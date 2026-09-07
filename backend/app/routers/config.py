"""Provider configuration endpoints.

Security rules:
  - API keys are accepted via POST and stored in process memory ONLY.
  - GET responses never contain key material — only has_key/source/tail + env defaults.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.providers import ProviderPayload, resolve_provider
from src.session_config import forget, set_key, status

router = APIRouter(prefix="/api/config", tags=["config"])


class KeyIn(BaseModel):
    slot: str            # "llm" | "embedding"
    api_key: str


@router.get("")
def get_status():
    return status()


@router.post("/key")
def set_api_key(body: KeyIn):
    set_key(body.slot, body.api_key)
    return {"ok": True, "slot": body.slot, "has_key": True}


@router.delete("/key")
def forget_keys():
    forget()
    return {"ok": True}


@router.post("/test")
async def test_connection(body: ProviderPayload):
    """Probe LLM (chat) and/or Embeddings endpoints with the effective config."""
    results = {}
    for slot in ("llm", "embedding"):
        fields = getattr(body, slot)
        if fields is None:
            continue
        p = resolve_provider(slot, fields)
        if not p.complete:
            results[slot] = {"ok": False, "error": "model_name and api_key required"}
            continue
        base = (p.base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {p.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if slot == "llm":
                    r = await client.post(
                        f"{base}/chat/completions",
                        json={"model": p.model_name,
                              "messages": [{"role": "user", "content": "ping"}],
                              "max_tokens": 1},
                        headers=headers,
                    )
                else:
                    r = await client.post(
                        f"{base}/embeddings",
                        json={"model": p.model_name, "input": ["dimension probe"]},
                        headers=headers,
                    )
                if r.status_code == 200:
                    data = r.json()
                    extra = {}
                    if slot == "embedding":
                        try:
                            dim = len(data["data"][0]["embedding"])
                            extra["embedding_dim"] = dim
                        except Exception:
                            pass
                    results[slot] = {"ok": True, "status": r.status_code, **extra}
                else:
                    results[slot] = {"ok": False, "status": r.status_code,
                                     "error": r.text[:300]}
        except Exception as e:  # noqa: BLE001
            results[slot] = {"ok": False, "error": str(e)[:300]}
    return results
