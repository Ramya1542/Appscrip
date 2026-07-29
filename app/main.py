"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import auth, chat, documents, health
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.middleware.exception_handler import ExceptionLoggingMiddleware
from app.services.cache import close_redis
from app.workers.kafka_producer import close_producer

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (env=%s)", settings.APP_NAME, __version__, settings.ENV)
    try:
        await init_db()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Database initialisation failed. Ensure PostgreSQL + pgvector are "
            "running and DATABASE_URL is correct."
        )
        raise
    yield
    # Shutdown: release external resources.
    await close_redis()
    await close_producer()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description="A FastAPI backend implementing JWT auth and a RAG pipeline "
    "(document ingestion, embeddings, vector retrieval and LLM answering).",
    lifespan=lifespan,
)

# Custom exception-logging middleware (persists unhandled errors to the DB).
app.add_middleware(ExceptionLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/", tags=["health"])
async def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
