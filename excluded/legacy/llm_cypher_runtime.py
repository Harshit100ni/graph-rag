from .config import settings

_graph = None
_chain = None

def get_cypher_chain():
    """Create GraphCypherQAChain lazily so server start doesn't depend on DB."""
    global _graph, _chain
    if _chain is not None:
        return _chain

    from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate

    _graph = Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_pass,
    )
    _graph.refresh_schema()

    llm = ChatOpenAI(model=settings.chat_model, temperature=0)

    cypher_prompt = ChatPromptTemplate.from_messages([
        ("system",
        # SAFETY
        "Write ONLY read-only Cypher: MATCH, OPTIONAL MATCH, WHERE, RETURN, ORDER BY, LIMIT.\n"
        "Never use CREATE, MERGE, DELETE, SET, REMOVE, CALL dbms.* or any schema write.\n\n"
        # SCHEMA SOURCE OF TRUTH
        "Use ONLY labels, relationship types, and properties that appear in this graph schema:\n{schema}\n\n"
        "Guidelines (schema-only, generic):\n"
        "- Use exact label and relationship names from the schema (case-sensitive in Cypher).\n"
        "- Only reference properties that exist in the schema for those labels.\n"
        "- When matching free-text user terms to string properties, prefer case-insensitive regex (e.g., '(?i)term').\n"
        "- If multiple relationship types could connect two nodes, you may use alternation (e.g., [:REL1|:REL2]).\n"
        "- Keep results compact and deduplicated: use DISTINCT and LIMIT (≤25).\n"
        "- When nodes have an identifier-like property (e.g., NodeID or name) visible in the schema, include it in RETURN.\n"
        "- Output ONLY a single Cypher query in a fenced code block (```cypher ... ```)."
        ),
        ("user", "Question: {question}")
    ])

    _chain = GraphCypherQAChain.from_llm(
        cypher_llm=llm,
        qa_llm=llm,
        graph=_graph,
        validate_cypher=True,           # blocks writes/admin ops
        allow_dangerous_requests=True,  # required by LangChain
        top_k=25,
        return_intermediate_steps=True,
        cypher_prompt=cypher_prompt,
    )
    return _chain
