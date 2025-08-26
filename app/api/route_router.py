from fastapi import APIRouter
from app.api.models import AskRouteIn, AskRouteOut
from app.services.ask_service import ask_fused
from app.services.fusion import fuse

router = APIRouter()

@router.post("/ask/route", response_model=AskRouteOut)
def ask_route(body: AskRouteIn):
    res = ask_fused(body.question, body.k, body.per_seed, body.org_limit)
    answer = fuse(body.question, res["cypher"]["result"], res["cypher"]["context"], res["facts"])
    return {
        "answer": answer or "I don’t know.",
        "question": body.question,
        "hybrid": {"facts": res["facts"], "citations": res["citations"], "triples": res["triples"]},
        "cypher": res["cypher"],
    }
