from openai import OpenAI
from .config import settings

_client = OpenAI(api_key=settings.openai_key)

def embed_texts(texts: list[str]) -> list[list[float]]:
    resp = _client.embeddings.create(model=settings.emb_model, input=texts)
    return [d.embedding for d in resp.data]

def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]
