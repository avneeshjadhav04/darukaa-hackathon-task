"""App entry: FastAPI API + static frontend.

Routes:
  /api/health, /api/config/*, /api/ingest/*, /api/chat/*
  /*          -> built frontend (docker: /app/static, dev: frontend/dist if present,
                 otherwise instructions to run the Vite dev server on :5173)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `from src.*` when running `uvicorn app.main:app` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import chat, config, ingest
from src.settings import DIST_DIR, STATIC_DIR
from src import db

app = FastAPI(title="AI Environmental Scientist", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(ingest.router)
app.include_router(chat.router)


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- static frontend ----------

def _static_root() -> Path | None:
    for d in (STATIC_DIR, DIST_DIR):
        if (d / "index.html").exists():
            return d
    return None


@app.get("/{path:path}")
def spa(path: str):
    root = _static_root()
    if root is None:
        return JSONResponse(
            {"detail": "frontend not built. For dev run: cd frontend && bun install && bun run dev "
                       "(Vite on :5173 proxies /api to :8000). Docker builds serve the bundle here."},
            status_code=404,
        )
    target = (root / path).resolve()
    if path and target.is_file() and str(target).startswith(str(root.resolve())):
        return FileResponse(target)
    return FileResponse(root / "index.html")
