"""Chroma vector store factory + embedding-dimension guard.

A single collection is shared across the app; it records the embedding dimension
of the model that created it. If a different embeddings provider/model is used
later (different dim), writes are rejected with a clear reset prompt.

The store is intentionally thin so another backend (e.g. Qdrant) could be
substituted behind `get_store()` later.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .settings import CHROMA_DIR

COLLECTION = "biodiversity"
_META_DIM = "embedding_dim"
_META_MODEL = "embedding_model"


class DimMismatchError(RuntimeError):
    def __init__(self, existing: int, incoming: int, model: str):
        super().__init__(
            f"index was built with embedding dim {existing}, but the configured "
            f"embeddings model ('{model}') produces dim {incoming}. "
            f"Reset the index and re-ingest, or restore the previous embeddings model."
        )
        self.existing = existing
        self.incoming = incoming


def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def make_embeddings(*, base_url: str, api_key: str, model: str) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url or None,   # None → OpenAI default
        check_embedding_ctx_length=False,  # provider-agnostic: don't assume tiktoken support
        chunk_size=64,
    )


def get_store(emb: OpenAIEmbeddings) -> Chroma:
    return Chroma(
        client=_client(),
        collection_name=COLLECTION,
        embedding_function=emb,
    )


def record_meta(dim: int, model: str) -> None:
    _write_meta(dim, model)


def _write_meta(dim: int, model: str) -> None:
    c = _client()
    col = c.get_or_create_collection(COLLECTION)
    md = dict(col.metadata or {})
    md[_META_DIM] = dim
    md[_META_MODEL] = model
    col.modify(metadata=md)


def read_meta() -> dict[str, Any]:
    c = _client()
    cols = [x.name for x in c.list_collections()]
    if COLLECTION not in cols:
        return {"dim": None, "model": "", "count": 0}
    col = c.get_collection(COLLECTION)
    md = col.metadata or {}
    return {
        "dim": md.get(_META_DIM),
        "model": md.get(_META_MODEL, ""),
        "count": col.count(),
    }


def check_dim_guard(emb: OpenAIEmbeddings, model: str) -> int:
    """Embed one probe string; verify dimension matches existing collection.

    Returns the embedding dimension. Raises DimMismatchError on conflict.
    """
    vec = emb.embed_documents(["dimension probe"])[0]
    dim = len(vec)
    meta = read_meta()
    if meta["dim"] and meta["count"] and int(meta["dim"]) != dim:
        raise DimMismatchError(int(meta["dim"]), dim, model)
    if not meta["dim"]:
        _write_meta(dim, model)
    return dim


def add_chunks(store: Chroma, chunks: list[str], metadatas: list[dict], ids: list[str]) -> None:
    store.add_texts(texts=chunks, metadatas=metadatas, ids=ids)


def delete_source(store: Chroma, name: str) -> int:
    col = _client().get_collection(COLLECTION)
    res = col.get(where={"source_name": name}, include=[])
    ids = res.get("ids") or []
    if ids:
        col.delete(ids=ids)
    return len(ids)


def reset_index() -> None:
    """Hard reset the collection (used after embeddings model change)."""
    c = _client()
    cols = [x.name for x in c.list_collections()]
    if COLLECTION in cols:
        c.delete_collection(COLLECTION)
