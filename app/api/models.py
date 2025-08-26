from pydantic import BaseModel

class AskRouteIn(BaseModel):
    question: str
    k: int = 8
    per_seed: int = 20
    org_limit: int = 25

class AskRouteOut(BaseModel):
    answer: str
    question: str
    hybrid: dict
    cypher: dict
