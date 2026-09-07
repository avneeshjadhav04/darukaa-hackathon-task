"""SQLite persistence for the single chat thread + index metadata.

Tables:
  messages(id, role, content, structured_json, created_at)   — chat history
  index_docs(name, kind, source, chunks, embedded_at)        — ingested sources

No provider secrets are ever stored here.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any

from .settings import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role TEXT NOT NULL,                     -- 'user' | 'assistant'
  content TEXT NOT NULL,
  structured_json TEXT,                   -- assistant structured payload (json) or user meta
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS index_docs (
  name TEXT PRIMARY KEY,
  kind TEXT NOT NULL,                     -- 'file' | 'url' | 'builtin'
  source TEXT,                            -- original filename / url
  chunks INTEGER NOT NULL,
  dim INTEGER,                            -- embedding dimension used
  created_at REAL NOT NULL
);
"""


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


# ---------------- messages ----------------

def add_message(role: str, content: str, structured: dict | None = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO messages(role, content, structured_json, created_at) VALUES(?,?,?,?)",
            (role, content, json.dumps(structured) if structured is not None else None, time.time()),
        )
        return int(cur.lastrowid)


def get_history(limit: int = 200) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, role, content, structured_json, created_at FROM messages ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "structured": json.loads(r["structured_json"]) if r["structured_json"] else None,
            "created_at": r["created_at"],
        })
    return out


def recent_turns(n: int = 12) -> list[tuple[str, str]]:
    """(role, content) pairs for the conversation window."""
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [(r["role"], r["content"]) for r in reversed(rows)]


def clear_messages() -> int:
    with _conn() as c:
        cur = c.execute("DELETE FROM messages")
        return cur.rowcount


# ---------------- index metadata ----------------

def upsert_index_doc(name: str, kind: str, source: str, chunks: int, dim: int | None) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO index_docs(name, kind, source, chunks, dim, created_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET chunks=excluded.chunks, dim=excluded.dim,
                                               kind=excluded.kind, source=excluded.source,
                                               created_at=excluded.created_at""",
            (name, kind, source, chunks, dim, time.time()),
        )


def list_index_docs() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT name, kind, source, chunks, dim, created_at FROM index_docs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_index_doc(name: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM index_docs WHERE name=?", (name,))
        return cur.rowcount > 0


def clear_index_docs() -> int:
    with _conn() as c:
        cur = c.execute("DELETE FROM index_docs")
        return cur.rowcount
