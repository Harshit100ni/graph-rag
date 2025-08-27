# app/services/cypher_qa.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import re

from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain

from app.prompts.cypher_prompt import _CYPHER_PROMPT
from app.core.settings import settings
from app.adapters.schema_reader import schema_snapshot, schema_text_for_llm

_CHAIN: Optional[GraphCypherQAChain] = None
_SCHEMA_TEXT: Optional[str] = None
_GRAPH: Optional[Neo4jGraph] = None

# One automatic repair attempt is usually enough to turn a syntax/runtime error
# into a good query when the model sees the Neo4j error text.
MAX_REPAIRS = 1


def _make_value_hints_text(max_labels: int = 10, max_examples_per_label: int = 10) -> str:
    snap = schema_snapshot()
    lines: List[str] = []
    used = 0
    for lab, meta in snap.get("label_props", {}).items():
        if used >= max_labels:
            break
        samples = meta.get("samples") or []
        # samples can be simple strings; if your schema_reader can provide prop:value pairs,
        # show them; otherwise just print the examples you have.
        if not samples:
            continue
        ex = ", ".join(samples[:max_examples_per_label])
        lines.append(f"- {lab} sample values: {ex}")
        used += 1
    return "\n".join(lines) if lines else "(no example values available)"

def _maybe_add_count_hint(q: str) -> str:
    """If user asks which/most/top/how many/etc, nudge toward COUNT/GROUP BY."""
    if re.search(r"\b(which|most|top|how many|count|largest|fewest|highest|lowest|rank|popular)\b", q, re.I):
        q += "\n\n(If applicable, use COUNT(DISTINCT ...) with GROUP BY and ORDER BY.)"
    return q


def _extract_generated_cypher(intermediate_steps: Any) -> Optional[str]:
    """GraphCypherQAChain puts generated query into intermediate steps ('query' or 'cypher')."""
    try:
        steps = intermediate_steps or []
        if not steps or not isinstance(steps[0], dict):
            return None
        return steps[0].get("cypher") or steps[0].get("query")
    except Exception:
        return None


def _format_context_preview(intermediate_steps: Any, max_rows: int = 40) -> str:
    """Render a compact preview of the rows the generated Cypher returned."""
    try:
        steps = intermediate_steps or []
        if not steps or not isinstance(steps[0], dict):
            return "(none)"
        ctx = steps[0].get("context") or []
        lines = []
        for i, row in enumerate(ctx[:max_rows], start=1):
            if isinstance(row, dict):
                keys = list(row.keys())[:8]
                kv = "; ".join([f"{k}={row.get(k)}" for k in keys])
                lines.append(f"{i}. {kv}")
            else:
                lines.append(f"{i}. {row}")
        return "\n".join(lines) if lines else "(none)"
    except Exception:
        return "(none)"


def get_chain(force_refresh_schema: bool = False) -> GraphCypherQAChain:
    """
    Initialize (or return cached) GraphCypherQAChain with schema/value hints
    baked into the prompt via .partial(...). The chain then only needs {'query': ...}.
    """
    global _CHAIN, _SCHEMA_TEXT, _GRAPH

    if _CHAIN is not None and not force_refresh_schema:
        return _CHAIN

    _GRAPH = Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_pass,
    )
    # If you ever want to force schema reload: _GRAPH.refresh_schema()

    snap = schema_snapshot()
    _SCHEMA_TEXT = schema_text_for_llm(snap)
    value_hints_text = _make_value_hints_text()

    cypher_llm = ChatOpenAI(model=settings.chat_model, temperature=0.1, api_key=settings.openai_key)
    qa_llm     = ChatOpenAI(model=settings.chat_model, temperature=0.2, api_key=settings.openai_key)

    prompt_partial = _CYPHER_PROMPT.partial(
        schema=_SCHEMA_TEXT or "(schema unavailable)",
        value_hints=value_hints_text or "(no example values available)",
    )

    _CHAIN = GraphCypherQAChain.from_llm(
        cypher_llm=cypher_llm,
        qa_llm=qa_llm,
        graph=_GRAPH,
        cypher_prompt=prompt_partial,
        allow_dangerous_requests=True,
        validate_cypher=True,
        return_intermediate_steps=True,
        top_k=25,
    )
    return _CHAIN


def _invoke_with_repair(chain: GraphCypherQAChain, q: str) -> Dict[str, Any]:
    """
    Invoke the chain once; on failure, append the Neo4j error text and ask
    the model to regenerate a corrected query (MAX_REPAIRS times).
    """
    attempts = 0
    last_err = None
    while attempts <= MAX_REPAIRS:
        try:
            return chain.invoke({"query": q})
        except Exception as e:
            last_err = e
            attempts += 1
            if attempts > MAX_REPAIRS:
                break
            # Feed the database error back to the LLM to fix the query.
            q = (
                q
                + "\n\nThe previously generated Cypher failed with this database error:\n"
                + f"{type(e).__name__}: {e}\n"
                + "Please regenerate ONE corrected Cypher query using ONLY the provided schema. "
                  "Return only the query (no explanations)."
            )
    # If we get here, repair failed
    raise last_err if last_err else RuntimeError("Unknown Cypher QA failure")


def run_cypher_qa(
    question: str,
    add_count_hint: bool = True,
    max_ctx_rows: int = 40,
    force_refresh_schema: bool = False,
) -> Dict[str, Any]:
    """
    Execute the Cypher QA chain with generic schema/value grounding and one repair attempt.
    Returns:
      - result: final answer (short)
      - cypher: generated query (if available)
      - steps: raw intermediate steps (for debugging)
      - context: compact preview of rows returned by the Cypher
    """
    chain = get_chain(force_refresh_schema=force_refresh_schema)

    q = question.strip()
    if add_count_hint:
        q = _maybe_add_count_hint(q)

    try:
        out: Dict[str, Any] = _invoke_with_repair(chain, q)
        steps = out.get("intermediate_steps") or []
        cypher_text = _extract_generated_cypher(steps) or "(unavailable)"
        ctx_preview = _format_context_preview(steps, max_rows=max_ctx_rows)
        result_text = out.get("result") or "I don't know."

        return {
            "result": result_text,
            "cypher": cypher_text,
            "steps": steps,
            "context": ctx_preview,
        }
    except Exception as e:
        # Never let a bad generated query 500 your API.
        return {
            "result": "I don't know.",
            "cypher": "(blocked due to invalid or unsafe query)",
            "steps": [{"error": f"{type(e).__name__}: {e}"}],
            "context": "(none)",
        }
