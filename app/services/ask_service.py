from app.retrievers.hybrid_generic import retrieve as hybrid_retrieve
from app.utils.facts import make_triple_facts
from app.services.cypher_qa import run_cypher_qa
from app.services.fusion import fuse_answer  
def ask_fused(question: str, k: int = 8, per_seed: int = 20, org_limit: int = 25):
    # 1. HYBRID triples
    triples = hybrid_retrieve(question, k=k, per_seed=per_seed, limit=org_limit)
    facts_text, citations = make_triple_facts(triples)

    # 2. CYPHER QA
    cy = run_cypher_qa(question)  

    # 3. Fuse into a final answer
    answer = fuse_answer(
        question=question,
        facts=facts_text,
        cypher_result=cy["result"],
        cypher_context=cy["context"],
        citations=citations,
    )

    return {
        "answer": answer,
        "question": question,
        "hybrid": {"facts": facts_text, "citations": citations, "triples": triples},
        "cypher": {
            "result": cy["result"],
            "cypher": cy["cypher"],
            "steps": cy["steps"],
            "context": cy["context"],
        },
    }
