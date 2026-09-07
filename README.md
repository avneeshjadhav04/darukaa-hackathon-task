# AI Environmental Scientist — Darukaa.Earth

A conversational **biodiversity intelligence** system, built for the Darukaa.Earth hackathon
challenge. It behaves like an applied environmental scientist: it gathers the variables it
needs, reasons across **multiple environmental metrics at once**, and returns **quantified,
source-cited** recommendations — not generic advice.

## What it does

| Requirement | How it's met |
|---|---|
| **Knowledge system** | ChromaDB vector store + curated **structured facts** table (quantified, FAO/IPCC-cited rules). Documents ingested via UI (file upload **or** URL fetch) — PDF/TXT/MD. Embedding-dimension guard prevents mixing providers. |
| **Conversational intelligence** | Slot tracker (region, soil OC, pH, moisture, rainfall, temperature, land use, crop, habitat, biodiversity indicator, human impact, water). Asks **clarifying questions** until ≥3 variables are known. SQLite thread survives browser refresh. |
| **Evidence-backed recommendations** | Pydantic-structured output forces every recommendation to carry: action · mechanism · impacted metrics · **quantified estimate** · time horizon · confidence · **citations**. |
| **Multi-metric reasoning** | The output schema **requires** `variables_connected ≥ 3` plus a causal chain linking them. |
| **Input handling** | Free text · structured JSON panel · optional geo coordinates. |
| **Output clarity** | Rendered as recommendation cards + streamed (SSE) + persisted single thread with Clear-Chat. |

## Architecture

```
┌──────────────────────── Single-screen UI (React + Bun/Vite) ───────────────────────┐
│  Sidebar:  Ingest Docs | Web-Fetch Fallback | Provider Config (LLM + Embeddings)   │
│  Main:     chat transcript (rec cards)  [Clear chat]  structured/JSON + geo  ⌁ SSE │
└──────────────────────────────────────┬─────────────────────────────────────────────┘
                                       │ REST + SSE (/api/*)
┌──────────────────────────────────────▼─────────────────────────────────────────────┐
│  FastAPI backend                                                                    │
│   routers: config · ingest · fetch · chat                                           │
│   src:     session_config (keys→memory) · vectorstore (Chroma+dim-guard)            │
│            ingest (chunk→embed→upsert) · chat (slots→clarify) · reasoning           │
│            (pydantic multi-metric chain) · db (SQLite: chat, index)                 │
└──────────────┬────────────────────────────────┬────────────────────────────────────┘
               ▼                                ▼
        ChromaDB (data/chroma)           SQLite (data/chat.db)
```

## Run it (one Docker command)

Requires **Docker** and, optionally, provider env vars (can also be set in the UI after boot).

```bash
docker build -t dbc .
docker run -p 8000:8000 -v dbc_data:/app/data dbc
# open http://localhost:8000
```

With providers pre-configured via environment:

```bash
docker run -p 8000:8000 -v dbc_data:/app/data \
  -e LLM_PROVIDER_NAME=openai \
  -e LLM_PROVIDER_BASE_URL=https://api.openai.com/v1 \
  -e LLM_PROVIDER_MODEL_NAME=gpt-4o-mini \
  -e LLM_PROVIDER_API_KEY=sk-... \
  -e EMBEDDING_PROVIDER_NAME=openai \
  -e EMBEDDING_PROVIDER_BASE_URL=https://api.openai.com/v1 \
  -e EMBEDDING_PROVIDER_MODEL_NAME=text-embedding-3-small \
  -e EMBEDDING_PROVIDER_API_KEY=sk-... \
  dbc
```

`docker-compose up` works too (convenience only).

### Provider config semantics
- **UI-managed, memory-only keys.** API keys you enter in the sidebar live only in server
  process memory (never written to disk/SQLite, never returned by any GET). They expire after
  ~30 min of inactivity and can be wiped with **Forget all keys**.
- **Env fallback.** `LLM_PROVIDER_*` and `EMBEDDING_PROVIDER_*` seed defaults and act as
  fallback keys. UI-set keys take precedence over env keys.
- **Non-secret fields persist** in your browser (`localStorage`), so refresh keeps your setup.
- Any **OpenAI-compatible** endpoint works (OpenAI, Azure, Ollama, local servers, etc.).

## Local development

Backend (FastAPI on :8000):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000
```

Frontend (Vite dev server on :5173, proxies `/api` → :8000):
```bash
cd frontend
bun install
bun run dev
```

Build the production bundle (served by FastAPI itself):
```bash
cd frontend && bun run build    # outputs frontend/dist, picked up by backend
```

## Validation

```bash
# No-API-key pipeline smoke test (mock LLM + embeddings):
python3 scripts/validate.py

# Real end-to-end with your providers (requires LLM_PROVIDER_*/EMBEDDING_PROVIDER_*):
python3 scripts/validate_live.py   # asks clarifications, then reasons + cites
```

`scripts/validate.py` proves the full path — slot extraction → ≥3-variable gate →
clarification → Chroma retrieval → structured pydantic answer with citations — with no
network or API key needed.

## Demo (expected flow)

1. **Configure providers** in the sidebar (LLM + Embeddings → Save & Test).
2. **Ingest** a couple of FAO/IPCC PDFs (or use Web-Fetch on a report page). Structured
   facts are auto-ingested with every upload.
3. **Chat** — try: *"Biodiversity is declining on my land."* → it asks for soil OC, rainfall,
   land use. Provide structured JSON like the challenge example:
   `{"soil_organic_carbon_pct":"0.3","rainfall":"low","crop":"monoculture wheat","region":"semi-arid"}`
   → expect agroforestry/intercropping recommendations with quantified estimates and FAO/IPCC citations.

## Security notes

- No provider secrets are stored in SQLite, files, logs, or `localStorage` — keys are
  memory-only on the server; only `has_key`/tail is ever shown.
- The challenge reference brief (`Reference Data/`) is git-ignored and not shipped.
