# app/auto_router.py

#Not preffered due to hard coding routing logics

import json, re
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI

from .config import settings
from .retrievers import semantic_knn, pattern_retriever, hybrid_retriever
from .facts import make_facts
from .llm import answer_from_facts

router = APIRouter()
_router_client = OpenAI(api_key=settings.openai_key)

# ---- Normalizers ----
_US_STATES = {
    "AL":"AL","ALABAMA":"AL","AK":"AK","ALASKA":"AK","AZ":"AZ","ARIZONA":"AZ","AR":"AR","ARKANSAS":"AR",
    "CA":"CA","CALIFORNIA":"CA","CO":"CO","COLORADO":"CO","CT":"CT","CONNECTICUT":"CT","DE":"DE","DELAWARE":"DE",
    "FL":"FL","FLORIDA":"FL","GA":"GA","GEORGIA":"GA","HI":"HI","HAWAII":"HI","ID":"ID","IDAHO":"ID","IL":"IL",
    "ILLINOIS":"IL","IN":"IN","INDIANA":"IN","IA":"IA","IOWA":"IA","KS":"KS","KANSAS":"KS","KY":"KY","KENTUCKY":"KY",
    "LA":"LA","LOUISIANA":"LA","ME":"ME","MAINE":"ME","MD":"MD","MARYLAND":"MD","MA":"MA","MASSACHUSETTS":"MA",
    "MI":"MI","MICHIGAN":"MI","MN":"MN","MINNESOTA":"MN","MS":"MS","MISSISSIPPI":"MS","MO":"MO","MISSOURI":"MO",
    "MT":"MT","MONTANA":"MT","NE":"NE","NEBRASKA":"NE","NV":"NV","NEVADA":"NV","NH":"NH","NEW HAMPSHIRE":"NH",
    "NJ":"NJ","NEW JERSEY":"NJ","NM":"NM","NEW MEXICO":"NM","NY":"NY","NEW YORK":"NY","NC":"NC","NORTH CAROLINA":"NC",
    "ND":"ND","NORTH DAKOTA":"ND","OH":"OH","OHIO":"OH","OK":"OK","OKLAHOMA":"OK","OR":"OR","OREGON":"OR","PA":"PA",
    "PENNSYLVANIA":"PA","RI":"RI","RHODE ISLAND":"RI","SC":"SC","SOUTH CAROLINA":"SC","SD":"SD","SOUTH DAKOTA":"SD",
    "TN":"TN","TENNESSEE":"TN","TX":"TX","TEXAS":"TX","UT":"UT","UTAH":"UT","VT":"VT","VERMONT":"VT","VA":"VA",
    "VIRGINIA":"VA","WA":"WA","WASHINGTON":"WA","WV":"WV","WEST VIRGINIA":"WV","WI":"WI","WISCONSIN":"WI","WY":"WY",
    "WYOMING":"WY"
}
def _norm_state(s: Optional[str]) -> Optional[str]:
    if not s: return None
    key = s.strip().upper()
    return _US_STATES.get(key, key if len(key) == 2 else None)

def _norm_cert(c: Optional[str]) -> Optional[str]:
    if not c: return None
    t = c.strip().lower()
    if "non" in t and "gmo" in t:
        return r"non[- ]?gmo"
    return t

def _norm_text(x: Optional[str]) -> Optional[str]:
    return x.strip() if x else None

# ---- Request model ----
class AutoAskBody(BaseModel):
    question: str
    prefer_mode: Optional[str] = None   # optional override: "pattern"|"hybrid"|"semantic"
    k: int = 8
    org_limit: int = 25

# ---- Router prompt (examples baked in) ----
_ROUTER_SYSTEM = (
    "You are an API router for a Graph-RAG system. "
    "Return ONLY JSON with keys: mode, state, crop, business_type, cert, k, org_limit. "
    "Routing rules:\n"
    "1) If explicit filters (state/crop/business_type/cert) appear → mode='pattern'.\n"
    "2) If user asks for seeds/candidates/top matches/similar only → mode='semantic'.\n"
    "3) Otherwise → mode='hybrid'.\n"
    "Normalization:\n"
    "- Use two-letter US state codes when applicable (e.g., 'Washington' → 'WA'), else state=null.\n"
    "- Any non-GMO phrasing → cert='non[- ]?gmo'.\n"
    "- Non-mentioned fields must be null. Defaults: k=8, org_limit=25."
)
_FEWSHOTS = [
    {"role":"user","content":"Show orgs in Washington storing beans with non-GMO certification"},
    {"role":"assistant","content":json.dumps({"mode":"pattern","state":"WA","crop":"beans","business_type":None,"cert":"non[- ]?gmo","k":8,"org_limit":25})},
    {"role":"user","content":"Give me top matches (seeds) for grain blenders in Oregon"},
    {"role":"assistant","content":json.dumps({"mode":"semantic","state":"OR","crop":None,"business_type":"blending","cert":None,"k":8,"org_limit":25})},
    {"role":"user","content":"Who handles pulses in the Pacific Northwest?"},
    {"role":"assistant","content":json.dumps({"mode":"hybrid","state":None,"crop":"pulses","business_type":None,"cert":None,"k":8,"org_limit":25})},
    {"role":"user","content":"List orgs with non-GMO beans (any state)"},
    {"role":"assistant","content":json.dumps({"mode":"pattern","state":None,"crop":"beans","business_type":None,"cert":"non[- ]?gmo","k":8,"org_limit":25})},
    {"role":"user","content":"blenders in OR"},
    {"role":"assistant","content":json.dumps({"mode":"pattern","state":"OR","crop":None,"business_type":"blending","cert":None,"k":8,"org_limit":25})},
]

def _route_with_llm(question: str) -> dict:
    messages = [{"role":"system","content":_ROUTER_SYSTEM}] + _FEWSHOTS + [{"role":"user","content":question}]
    resp = _router_client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        response_format={"type":"json_object"},
        messages=messages
    )
    # Parse router JSON
    try:
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        txt = resp.choices[0].message.content
        i, j = txt.find("{"), txt.rfind("}")
        data = json.loads(txt[i:j+1]) if i != -1 and j != -1 else {}

    # Normalize + defaults
    mode = (data.get("mode") or "hybrid").lower()
    state = _norm_state(data.get("state"))
    crop  = _norm_text(data.get("crop"))
    bt    = _norm_text(data.get("business_type"))
    cert  = _norm_cert(data.get("cert"))
    k     = int(data.get("k") or 8)
    org_limit = int(data.get("org_limit") or 25)

    # Safety flips
    if any([state, crop, bt, cert]) and mode != "pattern":
        mode = "pattern"
    if re.search(r"\b(seed|seeds|candidates|top matches|similar only)\b", question, re.I):
        mode = "semantic"

    return {"mode": mode, "state": state, "crop": crop, "business_type": bt,
            "cert": cert, "k": k, "org_limit": org_limit, "raw": resp.choices[0].message.content}

@router.post("/ask/auto")
def ask_auto(body: AutoAskBody):
    route = _route_with_llm(body.question)

    # Optional manual override
    if body.prefer_mode:
        route["mode"] = body.prefer_mode

    if route["mode"] == "semantic":
        seeds = semantic_knn(body.question, k=route["k"])
        seed_ids = [s["nodeId"] for s in seeds]
        return {"router_decision": route, "answer": None, "facts": [], "citations": seed_ids, "seeds": seeds}

    if route["mode"] == "pattern":
        rows = pattern_retriever(
            state=route["state"],
            crop=route["crop"],
            business_type=route["business_type"],
            cert=route["cert"],
            limit=route["org_limit"]
        )
    else:
        rows = hybrid_retriever(body.question, k=route["k"], org_limit=route["org_limit"])

    facts, citations = make_facts(rows)
    answer = answer_from_facts(body.question, facts) if rows else "I don’t know."
    return {"router_decision": route, "answer": answer, "facts": facts, "citations": citations}
