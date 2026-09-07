"""Ingest endpoints: file upload, URL fetch, index listing, reset."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src import db, ingest, vectorstore
from src.providers import ProviderFields, get_embeddings, resolve_provider
from src.vectorstore import check_dim_guard, get_store

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _embeddings_or_400(fields: ProviderFields | None):
    p = resolve_provider("embedding", fields)
    if not p.complete:
        raise HTTPException(
            400, "Embeddings provider not configured (model + key required). "
                 "Set it in the sidebar or via EMBEDDING_PROVIDER_* env vars.")
    emb = get_embeddings(p)
    try:
        dim = check_dim_guard(emb, p.model_name)
    except vectorstore.DimMismatchError as e:
        raise HTTPException(409, str(e)) from e
    return emb, dim


@router.post("/file")
async def ingest_file(file: UploadFile, payload: str = Form("{}")):
    fields = ProviderFields.model_validate_json(payload) if payload else None
    emb, dim = _embeddings_or_400(fields)
    store = get_store(emb)
    data = await file.read()
    try:
        result = ingest.ingest_bytes(store, filename=file.filename or "upload", data=data, dim=dim)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    # Always re-ingest builtin facts with the current index (idempotent ids)
    facts = ingest.ingest_structured_facts(store, dim=dim)
    return {"ok": True, "ingested": result, "structured_facts": facts}


class UrlIn(BaseModel):
    url: str
    embedding: ProviderFields | None = None


@router.post("/url")
def ingest_url(body: UrlIn):
    emb, dim = _embeddings_or_400(body.embedding)
    store = get_store(emb)
    try:
        result = ingest.ingest_url(store, url=body.url, dim=dim)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    facts = ingest.ingest_structured_facts(store, dim=dim)
    return {"ok": True, "ingested": result, "structured_facts": facts}


@router.get("/index")
def list_index():
    return {"docs": db.list_index_docs(), "collection": vectorstore.read_meta()}


class NameIn(BaseModel):
    name: str
    embedding: ProviderFields | None = None


@router.post("/delete")
def delete_doc(body: NameIn):
    emb, _ = _embeddings_or_400(body.embedding)
    store = get_store(emb)
    n = vectorstore.delete_source(store, body.name)
    db.delete_index_doc(body.name)
    return {"ok": True, "deleted_chunks": n}


@router.post("/reset")
def reset_index():
    vectorstore.reset_index()
    db.clear_index_docs()
    return {"ok": True}
