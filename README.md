# Graph-RAG (Neo4j + Fusion QA)

A production-minded Graph-RAG service that:

* stores your domain graph in **Neo4j**
* builds short **cards** per node → embeds them into a Neo4j **vector index**
* runs **two** retrieval paths:

  1. **Cypher-QA** (LLM generates Cypher from the live schema)
  2. **Hybrid** (semantic KNN → 1-hop expansion → compact FACTS)
* **fuses** both signals into a short, cited answer

> Main endpoint: `POST /ask/route` — returns the fused answer plus debug info (generated Cypher, FACTS, citations).

---

## Table of contents

* [Prerequisites](#prerequisites)
* [Environment](#environment)
* [Makefile workflow](#makefile-workflow)
* [API](#api)
* [How it works](#how-it-works)
* [Project layout](#project-layout)
* [Bring a different knowledge graph](#bring-a-different-knowledge-graph)
* [Tuning](#tuning)
* [Troubleshooting](#troubleshooting)
* [Security](#security)
* [License](#license)

---

## Prerequisites

* **Python** 3.10+
* **Neo4j** 5.25+ running locally or remotely
* **APOC** installed on Neo4j (needed for the `cards` script; runtime read paths are schema-agnostic)
* **OpenAI API key** (or swap the adapter)

> If you move the repo on disk, recreate your venv — paths inside `.venv` are not portable.

---

## Environment

Create a `.env` file in the repo root (used automatically by `make`):

```ini
# --- Neo4j ---
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASS=your_password

# --- OpenAI ---
OPENAI_API_KEY=sk-...
# Chat model for Cypher-QA + fusion (examples: gpt-4.1, gpt-4o-mini)
CHAT_MODEL=gpt-4.1
# Embedding model used by scripts.bootstrap_vectors (examples below)
EMB_MODEL=text-embedding-3-small
# Name of the native Neo4j vector index
VECTOR_INDEX=emb_card_idx
```

**Embedding dims (for your vector index):**

* `text-embedding-3-small` → 1536
* `text-embedding-3-large` → 3072

---

## Makefile workflow

List available targets:

```bash
make help
# make venv        # create venv
# make install     # pip install -r requirements.txt
# make run         # start API (uvicorn)
# make vectors     # build/refresh embeddings via LangChain Neo4jVector
# make cards       # regenerate node 'card' text (Cypher)
# make clean       # remove venv and pycache
```

### 1) Create the venv & install deps

```bash
make venv
make install
```

### 2) (Optional) Regenerate cards (concise text per node)

```bash
make cards
```

This runs `scripts/refresh_cards.cypher` via `cypher-shell` (APOC required).
Cards are used as the text source for embeddings.

### 3) Build/refresh embeddings & vector index

```bash
make vectors
```

This runs `scripts.bootstrap_vectors` using your `.env` values:

* reads `card` text from nodes,
* computes embeddings with `EMB_MODEL`,
* upserts vectors into the Neo4j native vector index `VECTOR_INDEX`.

> Ensure you created a compatible vector index (dims must match your `EMB_MODEL`).

### 4) Run the API

```bash
make run
# -> http://127.0.0.1:8000
```

OpenAPI docs: `http://127.0.0.1:8000/docs`

---

## API

### `POST /ask/route` — Fusion (Hybrid + Cypher-QA)

Runs hybrid retrieval **and** Cypher-QA, then fuses the evidence.

**Request:**

```json
{
  "question": "grain blenders in Oregon",
  "k": 8,
  "per_seed": 20,
  "org_limit": 25
}
```

* `k` — top-k semantic seeds (default 8)
* `per_seed` — max neighbors per seed in expansion (default 20)
* `org_limit` — final dedup cap (default 25)

**Quick tests:**

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

**Response (abridged):**

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
    "steps": [...],
    "context": "human-readable preview of rows"
  }
}
```

---

## How it works

1. **Hybrid (schema-agnostic)**

   * Embed the question → vector KNN over Neo4j’s native index.
   * Expand 1 hop with `apoc.path.expandConfig` using **runtime** label/relationship filters discovered from the live graph.
   * Convert `(a)-[rel]-(b)` into concise **FACTS** and `\[NodeID]` citations.

2. **Cypher-QA (schema-aware)**

   * Take a **live schema snapshot** (labels, relationship types, property names) + a small set of **example values**.
   * Use `GraphCypherQAChain` to generate Cypher, execute, and summarize rows.

3. **Fusion**

   * A strict system prompt fuses **CYRESULT + CYCONTEXT + FACTS** into a short answer.
   * If constraints aren’t fully satisfied, it says **“I don’t know.”**

---

## Project layout

```
app/
  adapters/
    openai_client.py
    schema_reader.py
  api/
    route_router.py          # POST /ask/route
  core/
    settings.py
  prompts/
    cypher_prompt.py
    fusion_prompt.py
  retrievers/
    semantic.py
    hybrid_generic.py
  services/
    ask_service.py
    cypher_qa.py
    embeddings.py
    fusion.py
  utils/
    facts.py
  main.py
scripts/
  refresh_cards.cypher        # rebuild node 'card' text
  bootstrap_vectors.py        # populate embeddings & vector index
```

> Older implementations were moved into an excluded folder; the current service is the **fusion** implementation.

---

## Bring a different knowledge graph

To swap in a new KG:

1. Load your nodes/edges in Neo4j.
2. Ensure searchable nodes have:

   * a stable **`NodeID`** (used for citations),
   * a short **`card`** string (used for embeddings),
   * an **`embedding`** property (float array),
   * are included in the vector index defined by `VECTOR_INDEX`.
3. Run:

   ```bash
   make cards     # (optional) if you need to regenerate card text
   make vectors   # to create/update embeddings
   make run
   ```

No code changes required — schema is discovered at runtime.

---

## Tuning

* **Embedding model** (`EMB_MODEL`):
  `text-embedding-3-small` (1536 dims, cheap/fast) or `…-large` (3072 dims, higher recall).
* **KNN seeds (`k`)**: try 6–12.
* **APOC expansion (`per_seed`)**: 10–30 per seed usually balances recall vs. noise.
* **`org_limit`**: 25–50 is often sufficient after dedup.
* **Chat temperature**: keep at **0** for deterministic, evidence-only answers.

---

## Troubleshooting

* **`OPENAI_API_KEY` missing** → the server logs an OpenAI error and answers “I don’t know.”
  Set it in `.env` or inline: `OPENAI_API_KEY=sk-... make vectors`.
* **APOC not found** when running `make cards` → install APOC and allowlist procedures you use.
* **Vector index dimension mismatch** → recreate the index with dims matching your `EMB_MODEL`.
* **Cypher-QA poor queries** → the service already supplies the live schema + value hints; re-ask with clearer constraints (e.g., state codes, exact business-type keywords). Fusion will prefer hard evidence.

---

## Security

* Use **read-only** Neo4j creds in production.
* Keep APOC allowlist minimal.
* Place the API behind auth if exposed publicly.

---

