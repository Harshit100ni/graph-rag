from fastapi import FastAPI
from pydantic import BaseModel
from .retrievers import semantic_knn, pattern_retriever, hybrid_retriever
from .facts import make_facts
from .llm import answer_from_facts
# from .auto_router import router as auto_router
# from .auto_router_llm import router as llm_tools_router
# from .ask_cypher import router as cypher_router
from .route_fusion import router as route_router

app = FastAPI(title="Graph-RAG Starter")

# app.include_router(auto_router)
# app.include_router(llm_tools_router)

# app.include_router(cypher_router)
app.include_router(route_router)

class AskBody(BaseModel):
    question: str
    mode: str = "hybrid"            # "hybrid" | "semantic" | "pattern"
    k: int = 8
    org_limit: int = 25
    state: str | None = None
    crop: str | None = None
    business_type: str | None = None
    cert: str | None = None

@app.post("/ask")
def ask(body: AskBody):
    if body.mode == "semantic":
        seeds = semantic_knn(body.question, k=body.k)
        seed_ids = [s["nodeId"] for s in seeds]
        return {"answer": None, "facts": [], "citations": seed_ids, "seeds": seeds}

    if body.mode == "pattern":
        rows = pattern_retriever(body.state, body.crop, body.business_type, body.cert)
    else:
        rows = hybrid_retriever(body.question, k=body.k, org_limit=body.org_limit)

    facts, citations = make_facts(rows)
    answer = answer_from_facts(body.question, facts)
    return {"answer": answer, "facts": facts, "citations": citations}
