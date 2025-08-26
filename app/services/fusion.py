from __future__ import annotations
from app.adapters.openai_client import make_chat
from app.prompts.fusion_prompt import FUSE_SYSTEM

_MAX_FACTS_CHARS = 6000
_MAX_CTX_CHARS = 6000
_MAX_RESULT_CHARS = 2000
_MAX_CITES = 40  # avoid giant prompts

def _clip(text: str | None, max_chars: int) -> str:
    if not text:
        return "(none)"
    t = text.strip()
    return t if len(t) <= max_chars else (t[: max_chars - 12] + "\n...[truncated]...")

def _has_any_fact(facts: str | None) -> bool:
    return bool(facts and ("- (" in facts or "FACTS" in facts))

def _has_text(x: str | None) -> bool:
    return bool(x and x.strip() and x.strip().lower() != "(none)")

def fuse_answer(
    *,
    question: str,
    facts: str,
    cypher_result: str | None,
    cypher_context: str | None,
    citations: list[str] | None = None,
) -> str:
    """
    Final answer = f(CYPHER_RESULT, CYPHER_CONTEXT, FACTS).
    Also provide whitelist of NodeIDs (CITATIONS) that the LLM is allowed to cite.
    """
    if not (_has_text(cypher_result) or _has_text(cypher_context) or _has_any_fact(facts)):
        return "I don't know."

    llm = make_chat()  # temperature=0 recommended

    # Dedup & cap citations for prompt hygiene
    cites = []
    seen = set()
    for cid in (citations or []):
        if cid and cid not in seen:
            seen.add(cid)
            cites.append(cid)
        if len(cites) >= _MAX_CITES:
            break

    cites_block = "CITATIONS (allowed NodeIDs):\n" + \
        ("\n".join(f"- {c}" for c in cites) if cites else "(none)")

    user = (
        f"QUESTION:\n{question.strip()}\n\n"
        f"CYRESULT:\n{_clip(cypher_result, _MAX_RESULT_CHARS)}\n\n"
        f"CYCONTEXT (rows):\n{_clip(cypher_context, _MAX_CTX_CHARS)}\n\n"
        f"{_clip(facts, _MAX_FACTS_CHARS)}\n\n"
        f"{cites_block}"
    )

    try:
        msg = llm.invoke([
            {"role": "system", "content": FUSE_SYSTEM},
            {"role": "user", "content": user},
        ])
        text = (getattr(msg, "content", "") or "").strip()
        if _has_text(text):
            return text

        # Fallbacks
        if _has_text(cypher_result):
            return cypher_result.strip()
        if _has_any_fact(facts):
            return "Here’s what I can confirm from the graph facts:\n" + _clip(facts, 1200)
        return "I don't know."
    except Exception:
        if _has_text(cypher_result):
            return cypher_result.strip()
        if _has_any_fact(facts):
            return "Here’s what I can confirm from the graph facts:\n" + _clip(facts, 1200)
        return "I don't know."
