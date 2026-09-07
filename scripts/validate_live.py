"""REAL end-to-end validation with configured providers.

Reads LLM_PROVIDER_*/EMBEDDING_PROVIDER_* env vars (or .env), runs the
challenge's semi-arid monoculture-wheat case against the full stack
(extraction -> clarification -> retrieval -> structured answer), and prints
the outcome + quality assertions.

Usage:
    cp .env.example .env   # fill in your keys   (or set env vars)
    python3 scripts/validate_live.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv()


def require(name):
    v = os.getenv(name, "").strip()
    if not v:
        sys.exit(f"Missing env var: {name}")
    return v


def main():
    from src import chat as chat_engine
    from src import db, ingest, vectorstore
    from src.providers import get_embeddings, get_llm, resolve_provider
    from src.vectorstore import check_dim_guard, get_store

    # --- resolve providers from env ---
    for slot, prefix in (("llm", "LLM_PROVIDER"), ("embedding", "EMBEDDING_PROVIDER")):
        for k in ("BASE_URL", "MODEL_NAME", "API_KEY"):
            require(f"{prefix}_{k}")
    lp = resolve_provider("llm", None)
    ep = resolve_provider("embedding", None)
    print(f"LLM: {lp.provider_name} / {lp.model_name}")
    print(f"Embeddings: {ep.provider_name} / {ep.model_name}")

    llm = get_llm(lp)
    emb = get_embeddings(ep)
    dim = check_dim_guard(emb, ep.model_name)
    print(f"embedding dim: {dim}")

    db.init_db()
    db.clear_messages()
    store = get_store(emb)
    facts = ingest.ingest_structured_facts(store, dim=dim)
    print(f"structured facts ingested: {facts['chunks']} chunks")

    # --- turn 1: sparse message -> expect clarifying questions ---
    print("\n>>> User: 'Biodiversity is declining on my land'")
    r1 = chat_engine.process_turn(llm=llm, store=store, message="Biodiversity is declining on my land")
    print(f"<<< [{r1['kind']}]\n{r1['content']}")
    if r1["kind"] != "clarify":
        print("NOTE: provider answered without clarifying (that's acceptable if it framed assumptions)")

    # --- turn 2: challenge's structured input -> expect grounded answer ---
    structured = {"soil_organic_carbon_pct": "0.3", "rainfall": "low",
                  "crop": "monoculture wheat", "region": "semi-arid"}
    print(f"\n>>> User: structured input {structured}")
    r2 = chat_engine.process_turn(llm=llm, store=store,
                                  message="What should I do to reverse biodiversity loss?",
                                  structured=structured)
    print(f"<<< [{r2['kind']}]\n{r2['content']}")

    if r2["kind"] == "answer":
        d = r2["data"]
        n = len(d["analysis"]["variables_connected"])
        has_num = any(any(ch.isdigit() for ch in r["quantified_estimate"]) for r in d["recommendations"])
        has_src = any(r["sources"] for r in d["recommendations"])
        print("\n--- quality checks ---")
        print(f"  variables connected: {n} ({'PASS' if n >= 3 else 'FAIL'} need >=3)")
        print(f"  quantified estimate present: {'PASS' if has_num else 'FAIL'}")
        print(f"  citations present: {'PASS' if has_src else 'FAIL'}")
        print(f"  retrieved sources used: {d.get('retrieved_sources')}")
        ok = n >= 3 and has_num and has_src
        print(f"\n=== {'LIVE VALIDATION PASSED' if ok else 'LIVE VALIDATION NEEDS REVIEW'} ===")


if __name__ == "__main__":
    main()
