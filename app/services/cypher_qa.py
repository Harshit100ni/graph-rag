from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from app.core.settings import settings
from app.adapters.openai_client import make_chat
from app.prompts.cypher_prompt import cypher_prompt

_graph = None
_chain = None

def get_chain():
    global _graph, _chain
    if _chain is not None:
        return _chain
    _graph = Neo4jGraph(url=settings.neo4j_uri, username=settings.neo4j_user, password=settings.neo4j_pass)
    _graph.refresh_schema()
    llm = make_chat()
    _chain = GraphCypherQAChain.from_llm(
        cypher_llm=llm, qa_llm=llm, graph=_graph,
        validate_cypher=True, allow_dangerous_requests=True,
        top_k=25, return_intermediate_steps=True, cypher_prompt=cypher_prompt,
    )
    return _chain
