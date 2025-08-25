# app/ask_cypher.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .config import settings
from langchain_core.prompts import ChatPromptTemplate

router = APIRouter()

_graph = None
_chain = None

class Body(BaseModel):
    question: str

def _get_chain():
    """Lazy init so import doesn't fail the whole server."""
    global _graph, _chain
    if _chain is not None:
        return _chain
    try:
        from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
        from langchain_openai import ChatOpenAI

        # Use your normal creds (Community edition has no RBAC)
        _graph = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_user,
            password=settings.neo4j_pass,
        )
        _graph.refresh_schema()

        llm = ChatOpenAI(model=settings.chat_model, temperature=0)

        cypher_prompt = ChatPromptTemplate.from_messages([
            ("system",
            "You write ONLY read-only Cypher: MATCH, OPTIONAL MATCH, WHERE, RETURN, "
            "ORDER BY, LIMIT. Never use CREATE, MERGE, DELETE, SET, REMOVE, CALL dbms.* "
            "or any schema writes. Use this graph schema:\n{schema}"),
            ("user", "Question: {question}")
        ])

        _chain = GraphCypherQAChain.from_llm(
            cypher_llm=llm,
            qa_llm=llm,
            graph=_graph,
            validate_cypher=True,          # blocks writes/admin ops
            allow_dangerous_requests=True, # REQUIRED by LangChain for LLM Cypher
            top_k=25,
            return_intermediate_steps=True,
            # extra nudge: read-only only
            cypher_prompt=cypher_prompt,
        )
        return _chain
    except Exception as e:
        # Surface a clear error at request time rather than crashing server on import
        raise HTTPException(status_code=500, detail=f"Cypher QA init failed: {e}")

@router.post("/ask/cypher")
def ask_cypher(body: Body):
    chain = _get_chain()
    out = chain.invoke({"query": body.question})
    return {"answer": out.get("result"),
            "intermediate_steps": out.get("intermediate_steps")}
