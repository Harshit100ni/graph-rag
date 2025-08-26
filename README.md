got it — here’s a cleaned-up, fully formatted **README** that keeps only the fusion flow and, per your note, uses your repo’s **existing backfill script** (no inline Python example).

---

# Graph-RAG (Fusion)

A small, production-minded **Graph-RAG** service on top of **Neo4j** + **APOC** that:

* does **semantic KNN** over node “cards” (Neo4j native vector index),
* expands **1 hop** generically via **APOC** (schema-agnostic),
* runs **LLM-generated Cypher QA** (no domain hardcoding),
* then **fuses** both evidence sources into a short, cited answer.

**One main endpoint:** `POST /ask/route`
It runs Hybrid + Cypher-QA and lets the LLM fuse the evidence into the final answer with **\[NodeID]** citations.

---

## Table of Contents

* [Features](#features)
* [Quickstart](#quickstart)

  * [Prerequisites](#prerequisites)
  * [Install](#install)
  * [Configure](#configure)
  * [Prepare the graph for RAG](#prepare-the-graph-for-rag)
  * [Run the server](#run-the-server)
* [API](#api)
* [How it works](#how-it-works)
* [Project layout](#project-layout)
* [Bring a different knowledge graph](#bring-a-different-knowledge-graph)
* [Tuning](#tuning)
* [Security](#security)
* [License](#license)

---

## Features

* **Schema-agnostic hybrid retrieval.** No hardcoded labels/relationship types.
* **Cited answers.** Inline citations using your nodes’ **`NodeID`**.
* **Evidence-only generation.** If facts are missing, the service says “I don’t know.”
* **Works with any KG** once you add `card` text, `embedding`, and a vector index.

---

## Quickstart

### Prerequisites

* **Python** 3.10+
* **Neo4j** 5.25+ (single instance is fine)
* **APOC** 5.x installed & enabled
* **OpenAI API key** (or swap the adapter to your provider)

> If you moved this repo on disk, **recreate your venv**—paths inside `.venv` break after moving folders.

### Install

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

**`requirements.txt` (pinned, compatible):**

```
# web
fastapi==0.115.0
uvicorn[standard]==0.30.6

# db + config
neo4j>=5.25,<6
pydantic-settings==2.4.0
python-dotenv==1.0.1
requests==2.32.3

# OpenAI SDK + transport
openai>=1.99.9,<2
httpx==0.27.2

# LangChain stack
langchain-neo4j==0.5.0
langchain>=0.3.7,<0.4.0
langchain-openai==0.3.31
```

### Configure

Create `.env` in repo root:

```ini
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASS=your_password
VECTOR_INDEX_NAME=emb_card_idx

# OpenAI
OPENAI_API_KEY=sk-...
EMB_MODEL=text-embedding-3-small   # 1536 dims
CHAT_MODEL=gpt-4o-mini             # chat model for Cypher-QA / fusion

# Server
HOST=0.0.0.0
PORT=8000
```

> For a single local Neo4j, prefer `bolt://` over `neo4j+s://` to avoid routing issues.

#### Enable APOC (Ubuntu packages)

1. Copy APOC JAR:

```bash
sudo cp ~/Downloads/apoc-5.*.jar /var/lib/neo4j/plugins/
sudo chown neo4j:neo4j /var/lib/neo4j/plugins/apoc-5.*.jar
```

2. Edit `/etc/neo4j/neo4j.conf`:

```
dbms.security.procedures.allowlist=apoc.coll.*,apoc.meta.*,apoc.path.*,apoc.text.*
dbms.security.procedures.unrestricted=apoc.meta.*,apoc.path.*
```

3. Restart:

```bash
sudo systemctl restart neo4j
sudo systemctl status neo4j
```

### Prepare the graph for RAG

You need three things on each searchable node:

1. **`card`** (short text summary) – used for embedding/search
2. **`:Embeddable`** label – to mark which nodes to embed
3. **`embedding`** (float array) – vector stored back on the node

#### 1) Create “cards” (example for organizations)

```cypher
MATCH (o:RyzosphereOrganization)
OPTIONAL MATCH (o)-[:HAS_STATE]->(s:State)
OPTIONAL MATCH (o)-[:HAS_BUSINESSTYPE]->(b:BusinessType)
OPTIONAL MATCH (o)-[:HANDLES_PRODUCT|STORES_PRODUCT]->(c:Crop)
OPTIONAL MATCH (o)-[:HAS_CERTIFICATION]->(cert:Certification)
WITH o,
     collect(DISTINCT coalesce(s.code, s.name)) AS states,
     collect(DISTINCT b.name) AS btypes,
     collect(DISTINCT c.name) AS crops,
     collect(DISTINCT cert.name) AS certs
SET o.card = trim(
  'Organization: ' + coalesce(o.name,'') +
  '; States: ' + apoc.text.join([x IN states WHERE x IS NOT NULL], ', ') +
  '; Business Types: ' + apoc.text.join([x IN btypes WHERE x IS NOT NULL], ', ') +
  '; Crops: ' + apoc.text.join([x IN crops WHERE x IS NOT NULL], ', ') +
  '; Certifications: ' + apoc.text.join([x IN certs WHERE x IS NOT NULL], ', ')
);
```

Create similar short `card` strings for other labels you want searchable.

#### 2) Mark nodes to embed

```cypher
MATCH (n) WHERE n.card IS NOT NULL SET n:Embeddable;
```

#### 3) Create the vector index

Choose dims based on your embedding model:

* `text-embedding-3-small` → **1536**
* `text-embedding-3-large` → **3072**

```cypher
CREATE VECTOR INDEX emb_card_idx IF NOT EXISTS
FOR (n:Embeddable) ON (n.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

#### 4) Backfill embeddings (use the repo’s script)

From repo root (with `.venv` active and `.env` set):

```bash
python3 backfill_embeddings.py
```

> The script reads `card` from `(:Embeddable)` nodes that have no `embedding`, calls your `EMB_MODEL`, and writes vectors back to `n.embedding`. It will resume safely if you rerun it.

### Run the server

```bash
# from repo root, venv active
uvicorn app.main:app --host $HOST --port $PORT --reload
# or
python -m app.main
```

OpenAPI docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API

### `POST /ask/route` — Fusion (Hybrid + Cypher-QA)

Runs both retrieval paths, then fuses them into a single answer.

**Request body:**

```json
{
  "question": "grain blenders in Oregon",
  "k": 8,
  "per_seed": 20,
  "org_limit": 25
}
```

* `k` (optional) — top-k seeds for semantic KNN (default: 8)
* `per_seed` (optional) — max paths per seed in APOC expand (default: 20)
* `org_limit` (optional) — final dedup cap (default: 25)

**Response (shape):**

```json
{
  "answer": "…short cited answer…",
  "question": "…",
  "hybrid": {
    "facts": "FACTS\n- (Label:Id) REL (Label:Id)\n…",
    "citations": ["Label:Id", "…"],
    "triples": [["A","REL","B"], …]
  },
  "cypher": {
    "result": "LLM summary of rows",
    "cypher": "generated cypher or '(blocked …)'",
    "steps": [
      { "query": "cypher ..." },
      { "context": [ { "col": "val" }, … ] }
    ],
    "context": "human preview of rows"
  }
}
```

**Try:**

```bash
curl -s http://127.0.0.1:8000/ask/route \
  -H 'Content-Type: application/json' \
  -d '{"question":"Which states have the most organizations?"}' | jq .

curl -s http://127.0.0.1:8000/ask/route \
  -H 'Content-Type: application/json' \
  -d '{"question":"grain blenders in Oregon"}' | jq .

curl -s http://127.0.0.1:8000/ask/route \
  -H 'Content-Type: application/json' \
  -d '{"question":"Show orgs in Washington storing beans with non-GMO certification"}' | jq .
```

---

## How it works

1. **Hybrid retrieval (schema-agnostic)**

   * Embed question → `db.index.vector.queryNodes(VECTOR_INDEX_NAME, k, qEmbedding)`
   * For each seed, expand **1 hop** using `apoc.path.expandConfig` with **runtime** `relationshipFilter` and `labelFilter` (discovered from the live graph).
   * Convert `(a)-[rel]-(b)` into compact **FACTS** and **\[NodeID]** citations.

2. **Cypher-QA (schema-aware, generic)**

   * Build a **live schema snapshot** (labels, rel-types, properties) + short **value hints** (example values).
   * Prompt an LLM (LangChain `GraphCypherQAChain`) to generate Cypher.
   * Execute the query; summarize rows into `result`.

3. **Fusion**

   * A strict **system prompt** fuses **CYRESULT + CYCONTEXT + FACTS** into a short answer with citations.
   * Evidence-only: if constraints aren’t fully satisfied or data is missing, it says “I don’t know.”

---

## Project layout

```
app/
  adapters/
    openai_client.py        # Chat + embeddings factories (OpenAI by default)
    schema_reader.py        # Live schema snapshot & formatting for LLM
  api/
    route_router.py         # POST /ask/route (fusion endpoint)
  core/
    settings.py             # pydantic-settings (env + defaults)
  prompts/
    cypher_prompt.py        # schema-aware, generic Cypher prompt
    fusion_prompt.py        # evidence-only fusion prompt
  retrievers/
    semantic.py             # KNN on Neo4j vector index
    hybrid_generic.py       # APOC expand (1 hop) with runtime rel/label filters
  services/
    ask_service.py          # orchestrates hybrid + cypher and shapes the response
    cypher_qa.py            # builds GraphCypherQAChain and executes
    fusion.py               # fuses evidence into final answer (with citations)
  utils/
    facts.py                # convert triples into "FACTS" text + NodeID citations
  main.py                   # FastAPI app bootstrap

backfill_embeddings.py      # <<< run this to create embeddings
```

*(Older implementations have been moved to an excluded folder for clarity.)*

---

## Bring a different knowledge graph

To swap in a new KG tomorrow:

1. Load nodes/edges in Neo4j.
2. Ensure nodes you want searchable have:

   * `NodeID` (human-readable, used for citations),
   * `card` (short text summary),
   * label `:Embeddable`,
   * `embedding` (float array).
3. Keep the vector index name in `.env` (e.g., `emb_card_idx`).
4. Start the service. It re-reads the live schema automatically.

No code changes required.

---

## Tuning

* **Embedding model**

  * `text-embedding-3-small` (1536 dims): fast/cheap, great default.
  * `text-embedding-3-large` (3072 dims): better recall; higher cost.
* **KNN seeds (`k`)**: 6–12 is a sweet spot.
* **APOC `per_seed`**: 10–30 neighbors per seed.
* **`org_limit`**: 25–50 is usually enough after de-dup.
* **Chat temperature**: keep **0** for deterministic, evidence-only answers.

---

## Security

* `GraphCypherQAChain` can generate arbitrary Cypher; **use read-only Neo4j credentials** in production.
* Keep the service behind auth if exposed.
* Limit APOC to what you need (we allowlist only `apoc.coll.*`, `apoc.meta.*`, `apoc.path.*`, `apoc.text.*`).

---
