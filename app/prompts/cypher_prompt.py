from langchain_core.prompts import ChatPromptTemplate

_CYPHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Write ONLY read-only Cypher using MATCH / OPTIONAL MATCH / WHERE / WITH / RETURN / ORDER BY / LIMIT / UNWIND / DISTINCT.\n"
     "NEVER call or reference any of: db.schema.*, db.labels(), db.relationshipTypes(), apoc.meta.*, apoc.schema.*, dbms.*.\n"
     "Do not try to introspect schema inside Cypher. Rely solely on the provided schema summary below.\n"
     "Use ONLY labels, relationship types, and properties that appear in this graph schema:\n{schema}\n\n"
     "When alternating relationship types, use -[:REL1|REL2]-> (single colon before the list).\n"
     "If you RETURN a variable, it MUST be introduced earlier in the query.\n"
     "If you use a relationship variable (e.g., r), you MUST bind it via a pattern like ()-[r]-().\n"
     "For free-text matches, use case-insensitive regex like '(?i).*term.*' or '(?i).*\\bterm\\b.*'.\n"
     "For 'which/most/top/how many' style questions, use COUNT(DISTINCT ...) with GROUP BY and ORDER BY.\n"
     "Keep results compact (LIMIT ≤ 25) and include identifier-like properties (NodeID/name/code) in RETURN.\n"
     "Output ONLY one query inside a ```cypher fenced block."),
    ("user",
     "Question: {question}\n\n"
     "Value hints (non-exhaustive):\n{value_hints}")
])
