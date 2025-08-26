from fastapi import APIRouter
from app.api.models import AskRouteIn, AskRouteOut
from app.services.ask_service import ask_fused
from app.services.fusion import fuse_answer

router = APIRouter()

@router.post("/ask/route", response_model=AskRouteOut)
def ask_route(body: AskRouteIn):
    # ask_fused already runs: hybrid → cypher → fuse
    return ask_fused(body.question, body.k, body.per_seed, body.org_limit)
   
