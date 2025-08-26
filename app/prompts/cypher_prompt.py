from langchain_core.prompts import ChatPromptTemplate

cypher_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Write ONLY read-only Cypher: MATCH / OPTIONAL MATCH / WHERE / RETURN / ORDER BY / LIMIT.\n"
     "Never use CREATE, MERGE, DELETE, SET, REMOVE, CALL dbms.* or schema writes.\n\n"
     "Use ONLY labels/relationship types/properties that appear in this graph schema:\n{schema}\n\n"
     "Generic tips: derive case-insensitive regex from user terms by stemming to roots "
     "(e.g., 'blenders' -> '(?i).*blend.*'; 'beans' -> '(?i).*\\bbeans?\\b.*'). "
     "Prefer DISTINCT and LIMIT ≤ 25. Output ONLY a single Cypher query in a ```cypher fenced block."
    ),
    ("user", "Question: {question}")
])
