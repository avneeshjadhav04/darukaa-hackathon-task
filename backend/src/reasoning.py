"""Reasoning layer: multi-metric, evidence-grounded structured output.

The chain REQUIRES recommendations that connect >=3 environmental variables,
carry quantified estimates, a time horizon, and citations to retrieved sources.
Output is a validated pydantic object — the chat layer never emits loose prose
for the recommendation itself.
"""
from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator


class Recommendation(BaseModel):
    action: str = Field(..., description="Specific intervention, e.g. 'introduce pigeonpea–wheat intercrop + Acacia senegal shelterbelts'")
    why: str = Field(..., description="Scientific mechanism: which processes link the variables")
    impacted_metrics: list[str] = Field(..., description="e.g. ['soil organic carbon', 'pollinator diversity']")
    quantified_estimate: str = Field(..., description="Magnitude + timeframe, e.g. 'SOC +0.4–0.6% over 3–5 years'")
    time_horizon: Literal["short", "medium", "long"] = Field(..., description="short=<1y, medium=1-3y, long=>3y")
    confidence: Literal["low", "medium", "high"]
    sources: list[str] = Field(..., description="Citations from RETRIEVED context (authors/org + year/title)")

    @field_validator("impacted_metrics", "sources")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("must be non-empty")
        return v


class Analysis(BaseModel):
    variables_connected: list[str] = Field(..., description=">=3 environmental variables reasoned jointly")
    causal_chain: str = Field(..., description="A→B→C narrative linking variables")
    clarifying_notes: str = Field("", description="Caveats, missing data, regional qualifiers")

    @field_validator("variables_connected")
    @classmethod
    def at_least_three(cls, v):
        if len(v) < 3:
            raise ValueError("must connect at least 3 environmental variables")
        return v


class ScientistResponse(BaseModel):
    analysis: Analysis
    recommendations: list[Recommendation] = Field(..., min_length=1)
    overall_confidence: Literal["low", "medium", "high"]


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an applied environmental scientist advising on biodiversity recovery. "
     "Reason ACROSS variables — never give single-variable advice. Ground every claim "
     "in the retrieved context. Cite specific sources from the context; if context is "
     "insufficient, say so rather than inventing citations. Numbers must come from the "
     "context or be clearly labelled as estimates with the mechanism stated.\n\n"
     "Known land/soil/climate context (slots collected so far):\n{slots}\n\n"
     "Retrieved evidence:\n{context}\n\n"
     "Conversation memory (recent turns):\n{history}"),
    ("human", "{question}"),
])


def build_chain(llm):
    return _PROMPT | llm.with_structured_output(ScientistResponse)


def format_slots(slots: dict) -> str:
    known = {k: v for k, v in slots.items() if v not in ("", None)}
    if not known:
        return "(none provided yet)"
    return "\n".join(f"- {k}: {v}" for k, v in sorted(known.items()))


def format_history(turns: list[tuple[str, str]]) -> str:
    if not turns:
        return "(no prior turns)"
    return "\n".join(f"{r}: {c}" for r, c in turns)
