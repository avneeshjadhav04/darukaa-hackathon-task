"""In-memory store for provider API keys.

Rules:
  - API keys live ONLY here (process memory). Never persisted to disk/SQLite.
  - `resolve()` merges: UI-supplied (in-memory) key > env var key.
  - A lightweight TTL sweep nulls keys after INACTIVITY_TTL_S without use.
"""
from __future__ import annotations

import time
from typing import Optional

from .settings import get_env_provider

INACTIVITY_TTL_S = 30 * 60          # 30 min default; keys re-entered in UI after expiry
_SLOTS = ("llm", "embedding")

_store: dict[str, dict] = {s: {"api_key": "", "last_used": 0.0} for s in _SLOTS}


def _norm_slot(slot: str) -> str:
    s = slot.strip().lower()
    if s in ("llm", "chat", "language"):
        return "llm"
    if s in ("embedding", "embeddings", "embed"):
        return "embedding"
    raise ValueError(f"unknown provider slot: {slot}")


def _sweep(now: Optional[float] = None) -> None:
    now = now or time.time()
    for v in _store.values():
        if v["api_key"] and now - v["last_used"] > INACTIVITY_TTL_S:
            v["api_key"] = ""
            v["last_used"] = 0.0


def set_key(slot: str, api_key: str) -> None:
    s = _norm_slot(slot)
    _store[s]["api_key"] = (api_key or "").strip()
    _store[s]["last_used"] = time.time()


def forget(slot: Optional[str] = None) -> None:
    """Clear one slot (or all) from memory."""
    _sweep()
    if slot is None:
        for s in _SLOTS:
            _store[s]["api_key"] = ""
            _store[s]["last_used"] = 0.0
        return
    s = _norm_slot(slot)
    _store[s]["api_key"] = ""
    _store[s]["last_used"] = 0.0


def resolve(slot: str) -> dict:
    """Return effective config for a slot.

    {provider_name, base_url, model_name, api_key, key_source: "ui"|"env"|""}
    Note: provider_name/base_url/model_name here are the ENV defaults only —
    the UI may override per request; merge happens at the call site.
    """
    _sweep()
    s = _norm_slot(slot)
    prefix = "EMBEDDING_PROVIDER" if s == "embedding" else "LLM_PROVIDER"
    env = get_env_provider(prefix)
    ui_key = _store[s]["api_key"]
    if ui_key:
        _store[s]["last_used"] = time.time()
    key = ui_key or env["api_key"]
    return {
        "provider_name": env["provider_name"],
        "base_url": env["base_url"],
        "model_name": env["model_name"],
        "api_key": key,
        "key_source": "ui" if ui_key else ("env" if env["api_key"] else ""),
    }


def status() -> dict:
    """Exposure-safe status for the UI (never exposes the key itself)."""
    _sweep()
    out = {}
    for s in _SLOTS:
        prefix = "EMBEDDING_PROVIDER" if s == "embedding" else "LLM_PROVIDER"
        env = get_env_provider(prefix)
        ui_key = _store[s]["api_key"]
        eff = ui_key or env["api_key"]
        out[s] = {
            "has_key": bool(eff),
            "key_source": "ui" if ui_key else ("env" if env["api_key"] else ""),
            "key_tail": ("..." + eff[-4:]) if eff else "",
            "env_defaults": {
                "provider_name": env["provider_name"],
                "base_url": env["base_url"],
                "model_name": env["model_name"],
            },
        }
    return out
