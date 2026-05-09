from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.retrieval.hybrid_search import get_hybrid_engine
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.utils.logger import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.api_title, version="1.0.0")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(chat_router)


@app.on_event("startup")
async def preload_retrieval() -> None:
    get_hybrid_engine()
