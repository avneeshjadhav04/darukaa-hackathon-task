"""Request-scoped provider config resolution.

Per request the UI may send {llm|embedding}.{provider_name,base_url,model_name}
plus `use_ui_key` (bool). Keys are attached from the in-memory store or env.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from .session_config import resolve
from .vectorstore import make_embeddings


class ProviderFields(BaseModel):
    provider_name: str = ""
    base_url: str = ""
    model_name: str = ""
    use_ui_key: bool = True          # send the key set via UI (memory) if present


class ProviderPayload(BaseModel):
    llm: ProviderFields | None = None
    embedding: ProviderFields | None = None


class ResolvedProvider(BaseModel):
    provider_name: str = ""
    base_url: str | None = None
    model_name: str = ""
    api_key: str = ""
    key_source: str = ""             # "ui" | "env" | ""

    @property
    def complete(self) -> bool:
        return bool(self.model_name and self.api_key)


def resolve_provider(slot: str, fields: ProviderFields | None) -> ResolvedProvider:
    base = resolve(slot)  # env defaults + effective key ({provider_name,base_url,model_name,api_key,key_source})
    out = dict(base)
    if fields:  # UI field values override env defaults (non-secret fields)
        for k in ("provider_name", "base_url", "model_name"):
            v = getattr(fields, k, "")
            if v:
                out[k] = v
        if not fields.use_ui_key and base["key_source"] == "ui":
            # caller asked not to use UI key -> fall back to env key
            from .settings import get_env_provider
            prefix = "EMBEDDING_PROVIDER" if slot == "embedding" else "LLM_PROVIDER"
            env = get_env_provider(prefix)
            out["api_key"] = env["api_key"]
            out["key_source"] = "env" if env["api_key"] else ""
    # Strip blanks so MissingKey handling falls to defaults, keep only meaningful overrides,
    # then fill any remaining from env defaults already in `out`.
    for k in ("provider_name", "base_url", "model_name"):
        if not out.get(k):
            out.pop(k, None)
    out["base_url"] = out.get("base_url") or None
    return ResolvedProvider(**out)


def get_llm(p: ResolvedProvider, *, streaming: bool = True, temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model=p.model_name,
        api_key=p.api_key,
        base_url=p.base_url,
        temperature=temperature,
        streaming=streaming,
    )


def get_embeddings(p: ResolvedProvider) -> OpenAIEmbeddings:
    return make_embeddings(base_url=p.base_url or "", api_key=p.api_key, model=p.model_name)
