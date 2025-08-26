import uvicorn
from fastapi import FastAPI
from app.core.settings import settings
from app.api.route_router import router as route_router

app = FastAPI(title="Graph-RAG")
app.include_router(route_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
