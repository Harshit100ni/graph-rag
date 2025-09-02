import uvicorn
from fastapi import FastAPI
from app.core.settings import settings
from app.api.route_router import router as route_router
from fastapi.middleware.cors import CORSMiddleware  # 👈 import CORS middleware

app = FastAPI(title="Graph-RAG")


# 👇 Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify your frontend URL: ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],  # allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # allows all headers
)


app.include_router(route_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
