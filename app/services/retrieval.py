"""Vector retrieval over stored chunks using pgvector cosine distance."""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embeddings import get_embedding_provider


@dataclass
class ScoredChunk:
    document_id: int
    chunk_index: int
    content: str
    score: float  # cosine similarity in [-1, 1]; higher = more relevant


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-python cosine similarity (used by retrieval fallbacks and tests)."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal length")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def retrieve_relevant_chunks(
    session: AsyncSession,
    query: str,
    owner_id: int,
    top_k: int | None = None,
    document_id: int | None = None,
) -> list[ScoredChunk]:
    """Embed ``query`` and return the ``top_k`` most similar chunks owned by the user.

    Uses the pgvector ``<=>`` cosine-distance operator (backed by the HNSW index)
    via SQLAlchemy's ``cosine_distance``. Similarity = 1 - distance.
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K

    provider = get_embedding_provider()
    query_vec = await provider.embed_query(query)

    distance = Chunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(Chunk, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.owner_id == owner_id)
    )
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    stmt = stmt.order_by(distance).limit(top_k)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ScoredChunk(
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=1.0 - float(dist),
        )
        for chunk, dist in rows
    ]
