# app/auto_router_llm.py
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from .config import settings
from .facts import make_triple_facts, answer_from_facts
from .retrievers_generic import hybrid_retriever_generic
from .llm_cypher_runtime import get_cypher_chain

router = APIRouter()
_client = OpenAI(api_key=settings.openai_key)

class RouteBody(BaseModel):
    question: str
    k: int = 8
    per_seed: int = 20
    org_limit: int = 25
    fallback_min_rows: int = 1   # if cypher returns < this, fallback to hybrid

_ROUTER_SYSTEM = (
    "You are a router for a Graph-RAG API. "
    "Return ONLY compact JSON with keys: strategy, k, per_seed, org_limit. "
    "strategy must be 'cypher' or 'hybrid'. "
    "Routing guidance:\n"
    "- If the query asks for precise graph constraints or joins (e.g., filters like state+crop+cert), choose 'cypher'.\n"
    "- If the query is fuzzy, exploratory, or benefit from semantic similarity, choose 'hybrid'.\n"
    "No prose, no comments; JSON only."
)

_FEWSHOTS = [
    # Precise constraints -> cypher
    {"role":"user","content":"Show orgs in Washington storing beans with non-GMO certification"},
    {"role":"assistant","content":json.dumps({"strategy":"cypher","k":8,"per_seed":20,"org_limit":25})},
    # Fuzzy discovery -> hybrid
    {"role":"user","content":"Who handles pulses in the Pacific Northwest?"},
    {"role":"assistant","content":json.dumps({"strategy":"hybrid","k":8,"per_seed":20,"org_limit":25})},
    # Seeds-ish but wants answer -> hybrid
    {"role":"user","content":"Find grain blenders in Oregon and summarize the top orgs"},
    {"role":"assistant","content":json.dumps({"strategy":"hybrid","k":8,"per_seed":20,"org_limit":25})},
]

def _route_decision(question: str, k: int, per_seed: int, org_limit: int) -> dict:
    msgs = [{"role":"system","content":_ROUTER_SYSTEM}] + _FEWSHOTS + [{"role":"user","content":question}]
    resp = _client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        response_format={"type":"json_object"},
        messages=msgs
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        txt = resp.choices[0].message.content
        i, j = txt.find("{"), txt.rfind("}")
        data = json.loads(txt[i:j+1]) if i != -1 and j != -1 else {}
    # defaults
    data.setdefault("strategy", "hybrid")
    data.setdefault("k", k)
    data.setdefault("per_seed", per_seed)
    data.setdefault("org_limit", org_limit)
    return data

@router.post("/ask/route")
def ask_route(body: RouteBody):
    route = _route_decision(body.question, body.k, body.per_seed, body.org_limit)
    strategy = (route.get("strategy") or "hybrid").lower()
    k        = int(route.get("k", body.k))
    per_seed = int(route.get("per_seed", body.per_seed))
    org_limit= int(route.get("org_limit", body.org_limit))

    if strategy == "cypher":
        # Run LLM-generated Cypher via Cypher QA chain
        chain = get_cypher_chain()
        out   = chain.invoke({"query": body.question})
        steps = out.get("intermediate_steps") or []
        cypher = None
        context_rows = []
        if steps and isinstance(steps[0], dict):
            cypher = steps[0].get("cypher")
            context_rows = steps[0].get("context") or steps[-1].get("context") or []

        # Fallback if not enough rows
        if len(context_rows) < body.fallback_min_rows:
            rows = hybrid_retriever_generic(body.question, k=k, per_seed=per_seed, org_limit=org_limit)
            facts, citations = make_triple_facts(rows)
            answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
            return {
                "router_decision": route,
                "strategy_used": "hybrid_fallback",
                "answer": answer,
                "facts": facts,
                "citations": citations,
                "triples": rows,
                "generated_cypher": cypher,
                "cypher_context_rows": context_rows,
            }

        # Cypher path succeeded
        return {
            "router_decision": route,
            "strategy_used": "cypher",
            "answer": out.get("result"),
            "facts": None,
            "citations": [],
            "generated_cypher": cypher,
            "cypher_context_rows": context_rows,
        }

    # Hybrid strategy
    rows = hybrid_retriever_generic(body.question, k=k, per_seed=per_seed, org_limit=org_limit)
    facts, citations = make_triple_facts(rows)
    answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
    return {
        "router_decision": route,
        "strategy_used": "hybrid",
        "answer": answer,
        "facts": facts,
        "citations": citations,
        "triples": rows
    }
