import os, time
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI  = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
EMB_MODEL  = os.getenv("EMB_MODEL", "text-embedding-3-large")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "200"))

# Sanity: pick expected dimension from model name
EXPECTED_DIMS = 3072 if "3-large" in EMB_MODEL else 1536

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
client  = OpenAI(api_key=OPENAI_KEY)

FETCH_QUERY = """
MATCH (n:Embeddable)
WHERE n.card IS NOT NULL AND n.embedding IS NULL
RETURN elementId(n) AS id, n.card AS text
LIMIT $batch
"""

SET_QUERY = """
MATCH (n) WHERE elementId(n) = $id
SET n.embedding = $vec
"""

def fetch_nodes(tx, batch):
    return list(tx.run(FETCH_QUERY, batch=batch))

def set_embedding(tx, node_id, vec):
    tx.run(SET_QUERY, id=node_id, vec=vec)

def get_index_dims(tx):
    q = """
    SHOW INDEXES YIELD name, options
    WHERE name = 'emb_card_idx'
    RETURN toInteger(options['indexConfig']['vector.dimensions']) AS dims
    """
    rec = tx.run(q).single()
    return rec["dims"] if rec else None

def main():
    with driver.session() as sess:
        dims = sess.execute_read(get_index_dims)
        if dims and dims != EXPECTED_DIMS:
            raise RuntimeError(
                f"Index dimension {dims} != expected {EXPECTED_DIMS} for {EMB_MODEL}. "
                "Fix the index or change the model."
            )

        total = 0
        while True:
            rows = sess.execute_read(fetch_nodes, BATCH_SIZE)
            if not rows:
                break

            texts = [r["text"] for r in rows]
            # Call embeddings API
            resp = client.embeddings.create(model=EMB_MODEL, input=texts)
            vectors = [d.embedding for d in resp.data]

            # Write back
            for rec, vec in zip(rows, vectors):
                sess.execute_write(set_embedding, rec["id"], vec)

            total += len(rows)
            print(f"Upserted {total} embeddings...")

            # Gentle pacing to avoid rate limits
            time.sleep(0.3)

    print("Done.")

if __name__ == "__main__":
    main()
