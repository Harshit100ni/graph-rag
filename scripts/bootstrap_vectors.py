# scripts/bootstrap_vectors.py
from __future__ import annotations

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector 

# If you already have a settings module, import from there:
# from app.core.settings import settings

# Or read from env directly:
import os

NEO4J_URI  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "password123")

# Use the same vector index name you query from in your app (e.g., 'emb_card_idx')
VECTOR_INDEX = os.getenv("VECTOR_INDEX", "emb_card_idx")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # must be set
EMB_MODEL = os.getenv("EMB_MODEL", "text-embedding-3-large")  # or -small to save cost

def main():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in environment.")

    embeddings = OpenAIEmbeddings(model=EMB_MODEL, api_key=OPENAI_API_KEY)

    Neo4jVector.from_existing_graph(
        embedding=embeddings,
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASS,
        index_name=VECTOR_INDEX,                # e.g., 'emb_card_idx'
        node_label="Embeddable",                # label of nodes to embed
        text_node_properties=["card"],          # REQUIRED: the text field to embed
        embedding_node_property="embedding",    # where to store the vector on node
        # Optional (only if you want to re-embed missing ones):
        # node_properties=["NodeID"],           # if you want to surface extra props in retrieval
        # search_type="vector",                 # default
    )

if __name__ == "__main__":
    main()
