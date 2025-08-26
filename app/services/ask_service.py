from app.retrievers.hybrid_generic import retrieve as hybrid_gen
from app.utils.facts import make_triple_facts
from app.services.cypher_qa import get_chain

def ask_fused(question: str, k=8, per_seed=20, org_limit=25, max_ctx_rows=40):
    # Hybrid
    rows = hybrid_gen(question, k=k, per_seed=per_seed, limit=org_limit)
    facts, cites = make_triple_facts(rows)
    # Cypher
    cy_res, cy_ctx_txt, cy_steps, cy_cypher = "(none)", "(none)", [], None
    try:
        out = get_chain().invoke({"query": question})
        cy_res = out.get("result") or "(none)"
        steps = out.get("intermediate_steps") or []
        cy_steps = steps
        if steps and isinstance(steps[0], dict):
            cy_cypher = steps[0].get("cypher")
            ctx = steps[0].get("context") or []
            # compress to rows of key=value
            lines = []
            for i, r in enumerate(ctx[:max_ctx_rows], 1):
                kv = "; ".join([f"{k}={r[k]}" for k in list(r.keys())[:8]]) if isinstance(r, dict) else str(r)
                lines.append(f"{i}. {kv}")
            cy_ctx_txt = "\n".join(lines) if lines else "(none)"
    except Exception as e:
        cy_res = f"(cypher error: {e})"

    return {
        "facts": facts, "citations": cites, "triples": rows,
        "cypher": {"result": cy_res, "cypher": cy_cypher, "steps": cy_steps, "context": cy_ctx_txt}
    }
