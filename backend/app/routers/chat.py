"""Chat endpoints: history, turn processing (SSE), clear."""
from __future__ import annotations

import json
import queue
import threading

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
def chat_stream(body: ChatIn):
    lp, key_source, store = _providers_or_400(body)
    llm = get_llm(lp, streaming=True)

    db.add_message("user", body.message, structured={"structured": body.structured,
                                                     "lat": body.lat, "lon": body.lon})

    def gen():
        yield _sse({"type": "start"})
        try:
            result = None
            chunk_q: "queue.Queue" = queue.Queue()

            def work():
                try:
                    r = chat_engine.process_turn(
                        llm=llm, store=store, message=body.message,
                        structured=body.structured, lat=body.lat, lon=body.lon)
                    chunk_q.put(("done", r))
                except Exception as e:  # noqa: BLE001
                    chunk_q.put(("error", e))

            t = threading.Thread(target=work, daemon=True)
            t.start()

            while True:
                kind, payload = chunk_q.get()
                if kind == "done":
                    result = payload
                    break
                raise payload

            # Record assistant message
            structured = result.get("data") if result["kind"] == "answer" else {
                "kind": "clarify", **(result.get("data") or {})}
            db.add_message("assistant", result["content"], structured=structured)

            # Stream the final content token-ish (sentence chunks keep it simple + robust)
            for chunk in result["content"].split("\n"):
                if chunk:
                    yield _sse({"type": "delta", "text": chunk + "\n"})
            yield _sse({"type": "final", "kind": result["kind"],
                        "data": result.get("data"), "slots": result.get("slots")})
        except Exception as e:  # noqa: BLE001
            yield _sse({"type": "error", "error": str(e)[:500]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
