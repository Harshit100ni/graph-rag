from fastapi import FastAPI
from pydantic import BaseModel
from .retrievers import semantic_knn, pattern_retriever, hybrid_retriever
from .facts import make_facts
from .llm import answer_from_facts
from .route_fusion import router as route_router

app = FastAPI(title="Graph-RAG Starter")

app.include_router(route_router)
