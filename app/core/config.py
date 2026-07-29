"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Application ---
    APP_NAME: str = "FastAPI RAG Backend"
    ENV: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: str = "*"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@localhost:5432/ragdb"

    # --- Auth ---
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # --- Embeddings ---
    EMBEDDING_PROVIDER: str = "local"  # local | voyage | openai
    EMBEDDING_MODEL: str = "local-hash-384"
    EMBEDDING_DIM: int = 384
    VOYAGE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # --- LLM (Anthropic) ---
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-5"
    # Note: on Claude Opus 5 thinking is on by default and shares this budget
    # with the answer text, so keep some headroom here.
    LLM_MAX_TOKENS: int = 4096

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # --- Ingestion ---
    INGEST_MODE: str = "background"  # sync | background | kafka
    CHUNK_SIZE: int = 200
    CHUNK_OVERLAP: int = 40
    RETRIEVAL_TOP_K: int = 5

    # --- Kafka ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_INGEST_TOPIC: str = "document.ingest"
    KAFKA_GROUP_ID: str = "rag-ingest-workers"

    @field_validator("EMBEDDING_PROVIDER", "INGEST_MODE")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Accept the plain Postgres URLs that managed hosts hand out.

        Render / Neon / Supabase expose `postgres://…` or `postgresql://…`,
        often with `?sslmode=require`. SQLAlchemy needs the `+asyncpg` driver,
        and asyncpg takes `ssl=` rather than libpq's `sslmode=`.
        """
        url = v.strip()
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+asyncpg://" + url[len(prefix) :]
                break

        parts = urlsplit(url)
        if not parts.query:
            return url

        params = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "sslmode":
                params.append(("ssl", value))
            elif key == "channel_binding":
                continue  # libpq-only; asyncpg rejects it
            else:
                params.append((key, value))
        return urlunsplit(parts._replace(query=urlencode(params)))

    @property
    def cors_origins_list(self) -> List[str]:
        raw = self.CORS_ORIGINS.strip()
        if raw == "*" or raw == "":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
