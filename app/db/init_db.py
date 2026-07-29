"""Database initialisation: extension, tables, and vector index."""
from __future__ import annotations

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import engine

# Ensure all models are imported so metadata is complete.
import app.models  # noqa: F401

logger = get_logger(__name__)


async def init_db() -> None:
    """Create the pgvector extension, all tables, and the vector index."""
    async with engine.begin() as conn:
        # 1. pgvector extension (idempotent).
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 2. Create all tables defined on the metadata.
        await conn.run_sync(Base.metadata.create_all)

        # 3. HNSW approximate-nearest-neighbour index on the embedding column
        #    using cosine distance. This is the index that powers retrieval.
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                "ON chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )

    logger.info("Database initialised (extension + tables + vector index).")
