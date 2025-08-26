# app/auto_router_llm.py
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from .config import settings
from .retrievers import semantic_knn, pattern_retriever, hybrid_retriever
from .facts import make_facts, make_triple_facts
from .llm import answer_from_facts
from .retrievers_generic import hybrid_retriever_generic
from .llm_cypher_runtime import get_cypher_chain

router = APIRouter()
client = OpenAI(api_key=settings.openai_key)

# -------- Request body --------
class RouteBody(BaseModel):
    question: str
    # optional knobs the model may also choose to use
    k: int = 8
    org_limit: int = 25

# -------- Define tools (functions) the LLM may call --------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_pattern",
            "description": "Use when the user specifies clear filters that must be satisfied together (AND).",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Two-letter US state code if applicable (e.g., WA)."},
                    "crop": {"type": "string", "description": "Crop filter (e.g., 'beans')."},
                    "business_type": {"type": "string", "description": "Business type filter (e.g., 'blending')."},
                    "cert": {"type": "string", "description": "Certification filter (e.g., 'non[- ]?gmo')."},
                    "org_limit": {"type": "integer", "description": "Max orgs to return", "default": 25}
                },
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_semantic",
            "description": "Use when the user wants seeds / candidates / top matches (vector KNN only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "k": {"type": "integer", "description": "Top-k seeds to return", "default": 8}
                },
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_hybrid",
            "description": "Use for open-ended natural language when no strict filters are requested.",
            "parameters": {
                "type": "object",
                "properties": {
                    "k": {"type": "integer", "description": "KNN seeds to fetch", "default": 8},
                    "org_limit": {"type": "integer", "description": "Max orgs after expansion", "default": 25}
                },
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "ask_cypher",
        "description": "Use when the question should be answered via LLM-generated Cypher over the live graph schema (no hardcoded query).",
        "parameters": {
        "type": "object",
        "properties": {
            "top_k": {"type":"integer","description":"Max rows for the Cypher chain to consider","default":25}
        },
        "required": [],
        "additionalProperties": False
        }
    }
    },
    {
    "type": "function",
    "function": {
        "name": "ask_hybrid_generic",
        "description": "Use for hybrid retrieval with generic 1-hop APOC expansion (no hardcoded rel types).",
        "parameters": {
        "type": "object",
        "properties": {
            "k": {"type":"integer","default":8},
            "per_seed": {"type":"integer","default":20},
            "org_limit": {"type":"integer","default":25}
        },
        "required": [],
        "additionalProperties": False
        }
    }
    }
]

SYSTEM = (
    "You are a router for a Graph-RAG API. "
    "Choose exactly ONE function to call and supply arguments the backend will execute as-is. "
    "Guidance: "
    "- If the user provides explicit filters (state/crop/business_type/cert) that must all hold, call ask_pattern. "
    "- If the user asks for 'seeds', 'top matches', or 'candidates', call ask_semantic. "
    "- Otherwise call ask_hybrid. "
    "Only call one function; do not output natural language."
)

@router.post("/ask/route")
def ask_route(body: RouteBody):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": body.question}
    ]

    resp = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        tools=TOOLS,
        tool_choice="auto",
        messages=messages,
    )

    choice = resp.choices[0]
    call = (choice.message.tool_calls or [None])[0]
    if call is None:
        raise HTTPException(status_code=400, detail="Router LLM did not choose a tool.")

    name = call.function.name
    args = json.loads(call.function.arguments or "{}")

    if name == "ask_semantic":
        k = int(args.get("k", body.k))
        seeds = semantic_knn(body.question, k=k)
        seed_ids = [s["nodeId"] for s in seeds]
        return {
            "router_tool": {"name": name, "args": args},
            "answer": None,
            "facts": [],
            "citations": seed_ids,
            "seeds": seeds
        }

    elif name == "ask_pattern":
        rows = pattern_retriever(
            state=args.get("state"),
            crop=args.get("crop"),
            business_type=args.get("business_type"),
            cert=args.get("cert"),
            limit=int(args.get("org_limit", body.org_limit))
        )
        facts, citations = make_facts(rows)
        answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
        return {
            "router_tool": {"name": name, "args": args},
            "answer": answer,
            "facts": facts,
            "citations": citations
        }

    elif name == "ask_hybrid":
        rows = hybrid_retriever(
            body.question,
            k=int(args.get("k", body.k)),
            org_limit=int(args.get("org_limit", body.org_limit))
        )
        facts, citations = make_facts(rows)
        answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
        return {
            "router_tool": {"name": name, "args": args},
            "answer": answer,
            "facts": facts,
            "citations": citations
        }
    
    elif name == "ask_cypher":
        # Let the chain write & run Cypher; we just return the result.
        top_k = int(args.get("top_k", 25))
        chain = get_cypher_chain()
        # NOTE: GraphCypherQAChain doesn’t take top_k at invoke time — the chain was created with top_k=25.
        out = chain.invoke({"query": body.question})
        # Optional: expose generated Cypher for debugging
        steps = out.get("intermediate_steps") or []
        cy = None
        if steps and isinstance(steps, list) and isinstance(steps[0], dict):
            cy = steps[0].get("cypher")
        return {
            "router_tool": {"name": name, "args": args},
            "answer": out.get("result"),
            "facts": None,
            "citations": [],
            "generated_cypher": cy,
            "intermediate_steps": steps,
        }

    elif name == "ask_hybrid_generic":
        k = int(args.get("k", body.k))
        per_seed = int(args.get("per_seed", 20))
        org_limit = int(args.get("org_limit", body.org_limit))
        rows = hybrid_retriever_generic(body.question, k=k, per_seed=per_seed, org_limit=org_limit)
        facts, citations = make_triple_facts(rows)
        answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
        return {
            "router_tool": {"name": name, "args": args},
            "answer": answer,
            "facts": facts,
            "citations": citations,
            "triples": rows
        }

    raise HTTPException(status_code=400, detail=f"Unknown tool selected: {name}")
