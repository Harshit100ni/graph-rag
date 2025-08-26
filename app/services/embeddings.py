from app.adapters.openai_client import make_embeddings

def embed_one(text: str) -> list[float]:
    return make_embeddings().embed_query(text)
