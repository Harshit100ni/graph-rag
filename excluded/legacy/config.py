from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_pass: str = os.getenv("NEO4J_PASS", "neo4j")
    vector_index: str = os.getenv("VECTOR_INDEX", "emb_card_idx")
    vector_dims: int = int(os.getenv("VECTOR_DIMS", "1536"))
    openai_key: str = os.getenv("OPENAI_API_KEY", "")
    emb_model: str = os.getenv("EMB_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")

settings = Settings()

