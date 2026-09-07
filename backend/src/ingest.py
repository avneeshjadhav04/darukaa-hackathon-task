"""Ingestion pipeline: file & URL -> text -> chunks -> embeddings -> Chroma.

Also ingests the curated structured-facts table (quantified, citation-bearing
rules) so numeric estimates are always grounded in a retrieved artefact.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Iterable

import trafilatura
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from . import db, vectorstore
from .settings import CHUNK_OVERLAP, CHUNK_SIZE, KNOWLEDGE_DIR, UPLOAD_DIR

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)

ALLOWED_FILE_EXT = {".pdf", ".txt", ".md"}


def _chunk(text: str) -> list[str]:
    return [c.strip() for c in _splitter.split_text(text) if c.strip()]


def _ids(name: str, chunks: list[str]) -> list[str]:
    return [hashlib.sha1(f"{name}:{i}:{c[:80]}".encode()).hexdigest() for i, c in enumerate(chunks)]


def _metas(name: str, kind: str, source: str, n: int) -> list[dict]:
    return [{"source_name": name, "kind": kind, "source": source, "chunk": i} for i in range(n)]


def extract_pdf(path: Path) -> str:
    r = PdfReader(str(path))
    parts = []
    for p in r.pages:
        t = p.extract_text() or ""
        if t.strip():
            parts.append(t)
    return "\n\n".join(parts)


def extract_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_url(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"could not fetch URL: {url}")
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
    if not text or not text.strip():
        raise ValueError(f"no extractable text at URL: {url}")
    return text


def _ingest_chunks(store: Chroma, *, name: str, kind: str, source: str, chunks: list[str],
                   dim: int) -> int:
    ids = _ids(name, chunks)
    metas = _metas(name, kind, source, len(chunks))
    vectorstore.add_chunks(store, chunks, metas, ids)
    db.upsert_index_doc(name, kind, source, len(chunks), dim)
    return len(chunks)


def ingest_bytes(store: Chroma, *, filename: str, data: bytes, dim: int) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_FILE_EXT:
        raise ValueError(f"unsupported file type '{ext}' (allowed: {sorted(ALLOWED_FILE_EXT)})")
    path = UPLOAD_DIR / f"{int(time.time())}_{Path(filename).name}"
    path.write_bytes(data)
    text = extract_pdf(path) if ext == ".pdf" else extract_text_file(path)
    if not text.strip():
        raise ValueError("no extractable text in document")
    chunks = _chunk(text)
    n = _ingest_chunks(store, name=Path(filename).name, kind="file",
                       source=str(path), chunks=chunks, dim=dim)
    return {"name": Path(filename).name, "kind": "file", "chunks": n}


def ingest_url(store: Chroma, *, url: str, dim: int) -> dict:
    text = extract_url(url)
    chunks = _chunk(text)
    name = url.split("://", 1)[-1][:120]
    n = _ingest_chunks(store, name=name, kind="url", source=url, chunks=chunks, dim=dim)
    return {"name": name, "kind": "url", "chunks": n}


def ingest_structured_facts(store: Chroma, *, dim: int) -> dict:
    """Load curated quantified rules and index them as individual documents."""
    fp = KNOWLEDGE_DIR / "structured_facts.json"
    if not fp.exists():
        return {"name": "structured_facts", "kind": "builtin", "chunks": 0}
    facts = json.loads(fp.read_text())
    chunks = []
    for f in facts:
        # One self-contained, retrieval-friendly sentence per fact.
        chunks.append(
            f"[structured-fact] intervention={f['intervention']} | context={f['context']} | "
            f"mechanism={f['mechanism']} | metric_effects={'; '.join(f['metric_effects'])} | "
            f"time_horizon={f['time_horizon']} | confidence={f['confidence']} | "
            f"source={f['source']}"
        )
    n = _ingest_chunks(store, name="structured_facts", kind="builtin",
                       source=str(fp), chunks=chunks, dim=dim)
    return {"name": "structured_facts", "kind": "builtin", "chunks": n}
