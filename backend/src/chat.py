"""Chat engine: slot extraction, clarifying questions, retrieval, answer.

Flow per turn (process_turn_stream, an async generator of events):
  1) extract environmental variable 'slots' from the message (+ prior history)
  2) if < MIN_VARS_FOR_ANSWER key variables are known -> ask targeted clarifications
  3) else -> retrieve relevant evidence -> stream the answer as narrative prose
     token-by-token -> structured post-pass builds the rec-card payload

Events yielded (kind, payload):
  ("status", stage)   stage in extracting|clarifying|retrieving|reasoning|structuring
  ("delta", text)     incremental answer text
  ("final", result)   {kind, content, data?, slots, parse_error?}

Slots and messages persist in SQLite so the thread survives browser refresh.
"""
from __future__ import annotations

import asyncio
import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from . import db
from .reasoning import (build_chain, build_stream_chain, format_history,
                        format_slots)

# Slot vocabulary — the variables the system tracks across the conversation.
SLOTS = [
    "region", "climate_zone", "soil_organic_carbon_pct", "soil_ph", "soil_moisture",
    "rainfall", "temperature", "land_use", "crop", "habitat_type",
    "biodiversity_indicator", "human_impact", "water_availability",
]
MIN_VARS_FOR_ANSWER = 3

_SLOTS_PATH = "slots.json"  # inside table, not a file; key below
_SLOT_KEY = "__slots__"


class Extracted(BaseModel):
    region: str = ""
    climate_zone: str = ""
    soil_organic_carbon_pct: str = ""
    soil_ph: str = ""
    soil_moisture: str = ""
    rainfall: str = ""
    temperature: str = ""
    land_use: str = ""
    crop: str = ""
    habitat_type: str = ""
    biodiversity_indicator: str = ""
    human_impact: str = ""
    water_availability: str = ""


_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Extract environmental variables from the user's message (consider recent history). "
     "Fill only fields explicitly stated or clearly implied; leave others empty. "
     "Use short normalised values, e.g. rainfall='low (~250mm/yr)', land_use='monoculture wheat'."),
    ("human", "Recent history:\n{history}\n\nNew message:\n{message}"),
])


class Clarify(BaseModel):
    questions: list[str] = Field(..., min_length=1, max_length=4)


_CLARIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an environmental scientist. The user needs biodiversity advice but key "
     "variables are missing. Ask 1-4 concise, targeted questions to obtain these missing "
     "variables: {missing}. Ask only what's needed; prefer the most diagnostic ones first. "
     "If a structured input panel or map is available, mention they can also provide JSON/coords."),
    ("human", "Known so far:\n{slots}\n\nUser message:\n{message}"),
])


# ---------- slot persistence ----------
# Slots are stored in a single synthetic assistant message row to reuse the
# messages table (keeps schema simple); tagged via structured_json.

def _slot_row() -> dict | None:
    hist = db.get_history(limit=500)
    for m in reversed(hist):
        if m["role"] == "assistant" and m["structured"] and m["structured"].get(_SLOT_KEY):
            return m
    return None


def load_slots() -> dict:
    row = _slot_row()
    if not row:
        return {k: "" for k in SLOTS}
    return {**{k: "" for k in SLOTS}, **row["structured"].get("values", {})}


def save_slots(slots: dict) -> None:
    db.add_message("assistant", "(slots updated)",
                   structured={_SLOT_KEY: True, "values": slots})


def merge_slots(existing: dict, new: dict) -> tuple[dict, list[str]]:
    """Merge non-empty new values into existing. Returns (merged, changed_keys)."""
    changed = []
    merged = dict(existing)
    for k, v in new.items():
        if k in SLOTS and v and str(v).strip() and not existing.get(k):
            merged[k] = str(v).strip()
            changed.append(k)
    return merged, changed


def known_count(slots: dict) -> int:
    return sum(1 for k in SLOTS if slots.get(k))


def missing_key_slots(slots: dict) -> list[str]:
    core = ["region", "land_use", "soil_organic_carbon_pct", "rainfall",
            "soil_ph", "crop", "biodiversity_indicator", "water_availability"]
    return [k for k in core if not slots.get(k)]


# ---------- turn processing ----------

def _apply_structured_input(slots: dict, structured: dict | None) -> dict:
    if not structured:
        return slots
    mapped, _ = merge_slots(slots, {k: structured.get(k, "") for k in SLOTS})
    # structured input may overwrite (explicit user intent)
    for k in SLOTS:
        v = structured.get(k)
        if v and str(v).strip():
            mapped[k] = str(v).strip()
    return mapped


def _apply_geo(slots: dict, lat: float | None, lon: float | None) -> dict:
    if lat is None or lon is None:
        return slots
    if not slots.get("region"):
        s = dict(slots)
        s["region"] = f"lat={lat:.3f}, lon={lon:.3f}"
        return s
    return slots


def process_turn(*, llm, store, message: str,
                 structured: dict | None = None,
                 lat: float | None = None, lon: float | None = None) -> dict:
    """Sync convenience wrapper: consume process_turn_stream, return the final event."""
    async def _run():
        result = None
        async for _kind, payload in process_turn_stream(
                llm=llm, store=store, message=message,
                structured=structured, lat=lat, lon=lon):
            if _kind == "final":
                result = payload
        if result is None:
            raise RuntimeError("turn produced no final event")
        return result

    return asyncio.run(_run())


async def process_turn_stream(*, llm, store, message: str,
                              structured: dict | None = None,
                              lat: float | None = None, lon: float | None = None):
    """Async generator: process one user turn, yielding events."""
    slots = load_slots()
    slots = _apply_structured_input(slots, structured)
    slots = _apply_geo(slots, lat, lon)

    history = db.recent_turns(12)
    q = message
    if structured:
        q += "\n[structured input] " + json.dumps(structured)
    if lat is not None and lon is not None:
        q += f"\n[geo] lat={lat}, lon={lon}"

    # 1) extraction
    yield "status", "extracting"
    extractor = _EXTRACTION_PROMPT | llm.with_structured_output(Extracted)
    extracted = await extractor.ainvoke({"history": format_history(history), "message": q})
    slots, changed = merge_slots(slots, extracted.model_dump())

    # 2) gate on variable count
    n = known_count(slots)
    if n < MIN_VARS_FOR_ANSWER:
        save_slots(slots)
        yield "status", "clarifying"
        clarifier = _CLARIFY_PROMPT | llm.with_structured_output(Clarify)
        missing = missing_key_slots(slots) or ["any 3 of: region, land_use, soil, rainfall"]
        out = await clarifier.ainvoke({
            "missing": ", ".join(missing),
            "slots": format_slots(slots),
            "message": q,
        })
        content = "\n".join(f"• {qq}" for qq in out.questions)
        for line in content.split("\n"):
            yield "delta", line + "\n"
        yield "final", {
            "kind": "clarify",
            "content": content,
            "data": {"questions": out.questions, "known": n, "needed": MIN_VARS_FOR_ANSWER},
            "slots": slots,
        }
        return

    # 3) retrieve + reason
    save_slots(slots)
    query = message + " " + " ".join(f"{k}={v}" for k, v in slots.items() if v)
    yield "status", "retrieving"
    docs = await asyncio.to_thread(store.similarity_search, query, 6) if store else []
    context = "\n\n---\n\n".join(
        f"source: {d.metadata.get('source_name','?')}\n{d.page_content}" for d in docs
    )

    # 3a) stream the narrative answer token-by-token
    yield "status", "reasoning"
    stream_chain = build_stream_chain(llm)
    parts: list[str] = []
    async for chunk in stream_chain.astream({
        "slots": format_slots(slots),
        "context": context or "(no documents indexed yet — answer from general scientific knowledge and flag the gap)",
        "history": format_history(history),
        "question": q,
    }):
        text = chunk.content if hasattr(chunk, "content") else str(chunk)
        if text:
            parts.append(text)
            yield "delta", text

    # 3b) structured post-pass for the rec-card payload
    yield "status", "structuring"
    narrative = "".join(parts)
    data: dict | None = None
    parse_error = ""
    try:
        chain = build_chain(llm)
        resp = await chain.ainvoke({
            "slots": format_slots(slots),
            "context": context or "(no documents indexed yet — answer from general scientific knowledge and flag the gap)",
            "history": format_history(history),
            "question": q,
        })
        payload = resp.model_dump()
        cited = sorted({d.metadata.get("source_name", "") for d in docs if d.metadata.get("source_name")})
        payload["retrieved_sources"] = cited
        data = payload
    except Exception as e:  # noqa: BLE001 — degrade to text-only answer
        parse_error = f"{type(e).__name__}: {e}"[:300]

    content = narrative if not parse_error else narrative + f"\n\n[structured summary unavailable: {parse_error}]"
    yield "final", {
        "kind": "answer",
        "content": content,
        "data": data,
        "parse_error": parse_error or None,
        "slots": slots,
    }
