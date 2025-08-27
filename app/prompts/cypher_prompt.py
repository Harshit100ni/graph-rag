from langchain.prompts import PromptTemplate

_CYPHER_PROMPT = PromptTemplate.from_template("""
You are a careful Cypher generator.

You MUST ONLY use labels, relationship types, and property names that appear in the SCHEMA below.
Do not invent labels, relationships, or properties.

Always:
- Use exact label and relationship names from the schema.
- Use WHERE filters with case-insensitive matching when the user gives strings:
  e.g., toLower(coalesce(n.code, n.name, n.canonical)) CONTAINS toLower('foo')
- Prefer `COUNT(DISTINCT ...)`, `GROUP BY`, `ORDER BY` for "which/most/top/how many".
- Return small, tidy columns with clear aliases. Always include LIMIT (<= 50).
- For alternate relationships, use the bracket form: `[:REL_A|REL_B]`.
- Never write data (no CREATE/MERGE/DELETE/SET/REMOVE).

SCHEMA (labels → properties, relationship types):
{schema}

EXAMPLE VALUES (to choose correct properties; not exhaustive):
{value_hints}

GENERIC PATTERNS (schema-agnostic examples):
- Filter nodes of a label by text:
  MATCH (n:SomeLabel)
  WHERE toLower(coalesce(n.name, n.code, n.canonical)) CONTAINS toLower($term)
  RETURN n LIMIT 25

- Count per related node:
  MATCH (a:LabelA)-[:REL_TYPE]->(b:LabelB)
  WITH b, COUNT(DISTINCT a) AS cnt
  RETURN b, cnt
  ORDER BY cnt DESC
  LIMIT 25

- Join with two constraints (different labels):
  MATCH (a:LabelA)-[:REL1]->(b:LabelB)
  MATCH (a)-[:REL2]->(c:LabelC)
  WHERE toLower(coalesce(b.name, b.code, b.canonical)) CONTAINS toLower($x)
    AND toLower(coalesce(c.name, c.code, c.canonical)) CONTAINS toLower($y)
  RETURN a, b, c
  LIMIT 25

- Return stable identifiers for citing, when present:
  coalesce(n.NodeID, labels(n)[0] + ':' + coalesce(n.code, n.name)) AS nodeId

Now write ONE Cypher query for the user’s question. Do not include explanations, only a fenced code block:

```cypher
-- your query
USER QUESTION:
{query}
""")