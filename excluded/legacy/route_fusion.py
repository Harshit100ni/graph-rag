# app/route_fusion.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Tuple
from langchain_openai import ChatOpenAI

from .config import settings
from .llm_cypher_runtime import get_cypher_chain
from .retrievers_generic import hybrid_retriever_generic
from .facts import make_triple_facts

router = APIRouter()

class RouteBody(BaseModel):
    question: str
    k: int = 8
    per_seed: int = 20
    org_limit: int = 25
    max_cypher_rows: int = 30   # cap context we show LLM
    max_fact_lines: int = 120   # cap for hybrid facts shown

def _rows_to_text(rows: List[Dict[str, Any]], limit: int = 30) -> str:
    """Format Cypher QA 'context' (list of dicts) into readable lines."""
    if not rows:
        return "(none)"
    out = []
    for i, r in enumerate(rows[:limit], 1):
        if isinstance(r, dict):
            pairs = [f"{k}={r[k]}" for k in list(r.keys())[:8]]
            out.append(f"{i}. " + "; ".join(pairs))
        else:
            out.append(f"{i}. {r}")
    if len(rows) > limit:
        out.append(f"... (+{len(rows)-limit} more)")
    return "\n".join(out)

def _truncate_facts(facts: str, max_lines: int) -> str:
    lines = facts.splitlines()
    if len(lines) <= max_lines:
        return facts
    return "\n".join(lines[:max_lines] + [f"... (+{len(lines)-max_lines} more lines)"])

FUSE_SYSTEM = (
    "You are a Graph-RAG answerer. You receive two evidence blocks:\n"
    "1) CYRESULT/CYCONTEXT from LLM-generated Cypher over the live graph.\n"
    "2) FACTS from a generic hybrid (vector→1-hop) expansion.\n\n"
    "Rules:\n"
    "- Prefer precise matches in CYCONTEXT when they directly satisfy the question.\n"
    "- Use FACTS to supplement and cross-check.\n"
    "- Answer ONLY from these sources. If insufficient, say “I don’t know.”\n"
    "- Cite NodeIDs in square brackets whenever present in FACTS (e.g., [RyzosphereOrganization:Acme]).\n"
    "- Keep the answer concise (1–6 sentences). Add a short 'Why these results' when helpful."
)

@router.post("/ask/route")
def ask_route(body: RouteBody):
    q = body.question

    # ---- 1) Generic hybrid retrieval (never fails if DB is up)
    rows_h = []
    facts_h = "FACTS\n- (none)"
    cites_h: List[str] = []
    try:
        rows_h = hybrid_retriever_generic(q, k=body.k, per_seed=body.per_seed, org_limit=body.org_limit)
        facts_h, cites_h = make_triple_facts(rows_h)
    except Exception as e:
        facts_h = f"FACTS\n- (error during hybrid retrieval: {e})"

    # ---- 2) Cypher QA (may fail if APOC meta not allowed, handle gracefully)
    cy_result = None
    cy_cypher = None
    cy_context_text = "(none)"
    cy_steps: List[Dict[str, Any]] = []
    try:
        chain = get_cypher_chain()
        out = chain.invoke({"query": q})
        cy_result = out.get("result")
        cy_steps = out.get("intermediate_steps") or []
        if cy_steps and isinstance(cy_steps[0], dict):
            cy_cypher = cy_steps[0].get("cypher")
            ctx = cy_steps[0].get("context") or []
            cy_context_text = _rows_to_text(ctx, limit=body.max_cypher_rows)
    except Exception as e:
        cy_result = f"(cypher qa error: {e})"

    # ---- 3) Fuse with a small LLM prompt
    fusion_llm = ChatOpenAI(model=settings.chat_model, temperature=0)

    user_block = (
        f"Question: {q}\n\n"
        f"CYRESULT:\n{cy_result or '(none)'}\n\n"
        f"CYCONTEXT (rows):\n{cy_context_text}\n\n"
        f"{_truncate_facts(facts_h, body.max_fact_lines)}\n"
    )

    messages = [
        {"role": "system", "content": FUSE_SYSTEM},
        {"role": "user", "content": user_block}
    ]
    final = fusion_llm.invoke(messages).content

    # ---- 4) Return everything useful for debugging/UI
    return {
        "answer": final if final else "I don’t know.",
        "question": q,
        "hybrid": {
            "facts": facts_h,
            "citations": cites_h,
            "triples": rows_h,
        },
        "cypher": {
            "result": cy_result,
            "generated_cypher": cy_cypher,
            "intermediate_steps": cy_steps,
        }
    }
