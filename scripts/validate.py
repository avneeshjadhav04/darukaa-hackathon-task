"""Local E2E smoke test for the reasoning/chat pipeline.

Uses MOCK LLM + MOCK embeddings — no API key or network needed — to prove the
pipeline wiring (extraction → gating → retrieval → structured reasoning → render).

For a REAL end-to-end check with your providers, run the app and use the UI,
or set LLM_PROVIDER_*/EMBEDDING_PROVIDER_* and run scripts/validate_live.py.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


class ScriptedChat(BaseChatModel):
    """Minimal mock that supports with_structured_output(schema) by always
    returning the next scripted dict validated against the schema."""

    scripts: list = []
    _idx: int = 0

    @property
    def _llm_type(self):
        return "scripted"

    def with_structured_output(self, schema, **kwargs):
        outer = self

        class _Runner(Runnable):
            def invoke(self, inputs, config=None, **kw):
                payload = outer.scripts[outer._idx]
                outer._idx += 1
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return schema.model_validate(payload)

        return _Runner()

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        payload = self.scripts[self._idx]
        self._idx += 1
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


class MockEmb(Embeddings):
    DIM = 32

    def embed_documents(self, texts):
        return [[float((abs(hash(t)) >> i) % 7 + 1) for i in range(self.DIM)] for t in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def main():
    from src import chat as chat_engine
    from src import db, ingest, vectorstore

    # fresh state for the test
    db.init_db()
    db.clear_messages()
    vectorstore.reset_index()
    db.clear_index_docs()

    # --- turn 1: sparse message -> expect clarification ---
    llm = ScriptedChat(scripts=[
        {"region": "", "climate_zone": "", "soil_organic_carbon_pct": "",
         "soil_ph": "", "soil_moisture": "", "rainfall": "", "temperature": "",
         "land_use": "cropland", "crop": "", "habitat_type": "",
         "biodiversity_indicator": "declining", "human_impact": "", "water_availability": ""},
        {"questions": ["What is your soil organic carbon %?", "What is your rainfall pattern?", "Which crop/land-use is this?"]},
    ])
    r1 = chat_engine.process_turn(llm=llm, store=None, message="Biodiversity is declining on my land")
    assert r1["kind"] == "clarify", f"expected clarify, got {r1['kind']}"
    print("✓ turn-1 clarification gate works (asked", len(r1['data']['questions']), "questions)")

    # --- turn 2: structured input completes slots -> expect answer with citations ---
    emb = MockEmb()
    store = vectorstore.get_store(emb)
    dim = vectorstore.check_dim_guard(emb, "mock-emb")
    ingest.ingest_structured_facts(store, dim=dim)
    print("✓ structured facts ingested:", db.list_index_docs()[0]["chunks"], "chunks")

    llm2 = ScriptedChat(scripts=[
        {"region": "semi-arid, Deccan plateau", "climate_zone": "", "soil_organic_carbon_pct": "",
         "soil_ph": "", "soil_moisture": "", "rainfall": "", "temperature": "",
         "land_use": "", "crop": "", "habitat_type": "",
         "biodiversity_indicator": "", "human_impact": "", "water_availability": ""},
        # streamed narrative (phase 1) — what the LLM would emit token-by-token
        "Analysis: Continuous wheat on 0.3% SOC under low rainfall links soil organic "
        "carbon, rainfall, land use and biodiversity in one causal chain: low SOC "
        "degrades structure and microbial biomass, monoculture removes pollinator "
        "forage, and low rainfall prevents recovery.\n"
        "Recommendations:\n"
        "1. Shift to pigeonpea–wheat rotation with hedgerow strips\n"
        "   Why: Legume N-fixation + residue raise SOC; hedgerows add habitat "
        "connectivity and pollinator forage.\n"
        "   Improves: soil organic carbon, pollinator diversity — SOC +15–25% over "
        "2–3 years; pollinators +50–70%\n"
        "   Horizon: medium | Confidence: high\n"
        "   Sources: FAO (2017) VGSSM, structured_facts\n"
        "Overall confidence: high",
        # structured post-pass (phase 2) — validated against ScientistResponse
        {
            "analysis": {
                "variables_connected": ["soil organic carbon", "rainfall", "land use", "biodiversity"],
                "causal_chain": "Continuous wheat on 0.3% SOC under low rainfall degrades soil structure, suppresses microbial biomass, and removes pollinator forage.",
                "clarifying_notes": "Consider local pigeonpea varieties."
            },
            "recommendations": [{
                "action": "Shift to pigeonpea–wheat rotation with hedgerow strips",
                "why": "Legume N-fixation + residue raise SOC; hedgerows add habitat connectivity and pollinator forage.",
                "impacted_metrics": ["soil organic carbon", "pollinator diversity", "habitat connectivity"],
                "quantified_estimate": "SOC +15–25% over 2–3 years; pollinators +50–70%",
                "time_horizon": "medium",
                "confidence": "high",
                "sources": ["FAO (2017) VGSSM", "structured_facts"]
            }],
            "overall_confidence": "high"
        },
    ])
    r2 = chat_engine.process_turn(
        llm=llm2, store=store, message="still declining",
        structured={"soil_organic_carbon_pct": "0.3", "rainfall": "low",
                    "crop": "monoculture wheat", "region": "semi-arid"})
    assert r2["kind"] == "answer", f"expected answer, got {r2['kind']}"
    data = r2["data"]
    assert data, "structured payload missing (post-pass failed)"
    assert len(data["analysis"]["variables_connected"]) >= 3, "must connect >=3 vars"
    assert data["recommendations"][0]["quantified_estimate"], "needs numeric estimate"
    assert data["recommendations"][0]["sources"], "needs citations"
    assert "Recommendations:" in r2["content"], "streamed narrative should be in content"
    print("✓ turn-2 answer produced: connects", len(data["analysis"]["variables_connected"]),
          "vars,", len(data["recommendations"]), "recommendations, sources:", data["recommendations"][0]["sources"])
    print("\n--- streamed narrative (content) ---\n")
    print(r2["content"])
    print("\n--- structured payload (rec cards) ---")
    print(json.dumps(data["analysis"], indent=2))
    print("\n=== mock pipeline OK ===")


if __name__ == "__main__":
    main()
