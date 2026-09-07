"""Chat endpoints: history, turn processing (SSE), clear."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src import chat as chat_engine
from src import db, vectorstore
from src.providers import (ProviderFields, get_embeddings, get_llm,
                             resolve_provider)
from src.vectorstore import get_store

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatIn(BaseModel):
    message: str
    structured: dict | None = None        # structured (JSON) input
    lat: float | None = None
    lon: float | None = None
    llm: ProviderFields | None = None
    embedding: ProviderFields | None = None


@router.get("/history")
def history():
    msgs = [m for m in db.get_history(500)
            if not (m["structured"] and m["structured"].get("__slots__"))]
    return {"messages": msgs, "slots": chat_engine.load_slots()}


@router.post("/clear")
def clear():
    n = db.clear_messages()
    return {"ok": True, "deleted": n}


def _providers_or_400(body: ChatIn):
    lp = resolve_provider("llm", body.llm)
    if not lp.complete:
        raise HTTPException(400, "LLM provider not configured (model + key required). "
                                 "Set it in the sidebar or via LLM_PROVIDER_* env vars.")
    ep = resolve_provider("embedding", body.embedding)
    emb = get_embeddings(ep) if ep.complete else None
    store = get_store(emb) if emb is not None else None
    return lp, lp.key_source, store


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/stream")
async def chat_stream(body: ChatIn):
    lp, key_source, store = _providers_or_400(body)
    llm = get_llm(lp, streaming=True)

    db.add_message("user", body.message, structured={"structured": body.structured,
                                                     "lat": body.lat, "lon": body.lon})

    async def gen():
        yield _sse({"type": "start"})
        result = None
        try:
            async for kind, payload in chat_engine.process_turn_stream(
                    llm=llm, store=store, message=body.message,
                    structured=body.structured, lat=body.lat, lon=body.lon):
                if kind == "status":
                    yield _sse({"type": "status", "stage": payload})
                elif kind == "delta":
                    yield _sse({"type": "delta", "text": payload})
                elif kind == "final":
                    result = payload
                    break
            if result is None:
                raise RuntimeError("turn produced no final event")

            # Record assistant message
            structured = result.get("data") if result["kind"] == "answer" else {
                "kind": "clarify", **(result.get("data") or {})}
            db.add_message("assistant", result["content"], structured=structured)

            yield _sse({"type": "final", "kind": result["kind"],
                        "data": result.get("data"), "slots": result.get("slots"),
                        "parse_error": result.get("parse_error")})
        except Exception as e:  # noqa: BLE001
            yield _sse({"type": "error", "error": str(e)[:500]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})