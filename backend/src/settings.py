"""Runtime settings & provider configuration.

Provider credentials come from two sources (precedence: UI in-memory > env vars):
  - Env vars: LLM_PROVIDER_NAME, LLM_PROVIDER_BASE_URL, LLM_PROVIDER_MODEL_NAME,
              LLM_PROVIDER_API_KEY  (+ EMBEDDING_PROVIDER_* equivalents)
  - UI: set at runtime, held in process memory only (api keys are NEVER persisted).

Non-secret UI fields (name/base_url/model) are persisted client-side by the
frontend (localStorage) and re-sent each request; the server keeps no copy of
secrets on disk, in SQLite, or in logs.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
# Local dev:  ROOT = repo root (this file is backend/src/settings.py -> 3 parents up)
# Docker:     backend/ is copied to /app/ -> this file is /app/src/settings.py, which
#             would wrongly resolve to "/". APP_ROOT env pins the app root explicitly.
ROOT = Path(os.getenv("APP_ROOT", str(Path(__file__).resolve().parent.parent.parent))).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
CHROMA_DIR = DATA_DIR / "chroma"
UPLOAD_DIR = DATA_DIR / "uploads"
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", str(DATA_DIR / "knowledge")))
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "chat.db")))
STATIC_DIR = ROOT / "static"          # built frontend (Docker)
DIST_DIR = ROOT / "frontend" / "dist"  # dev convenience

for _d in (DATA_DIR, CHROMA_DIR, UPLOAD_DIR, KNOWLEDGE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Chunking parameters used by the ingestion pipeline
CHUNK_SIZE = 900
CHUNK_OVERLAP = 140


def get_env_provider(prefix: str) -> dict:
    """Read one provider block from the environment.

    prefix: "LLM_PROVIDER" or "EMBEDDING_PROVIDER"
    Returns dict with provider_name/base_url/model_name/api_key ("" when unset).
    """
    return {
        "provider_name": os.getenv(f"{prefix}_NAME", "").strip(),
        "base_url": os.getenv(f"{prefix}_BASE_URL", "").strip(),
        "model_name": os.getenv(f"{prefix}_MODEL_NAME", "").strip(),
        "api_key": os.getenv(f"{prefix}_API_KEY", "").strip(),
    }


def env_provider_complete(prefix: str) -> bool:
    p = get_env_provider(prefix)
    # base_url + model + key are the hard requirements; provider_name is cosmetic
    return bool(p["base_url"] and p["model_name"] and p["api_key"])
