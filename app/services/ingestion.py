"""Document ingestion pipeline.

Flow: store document -> chunk text -> generate embeddings -> store chunks.

Three modes (INGEST_MODE):
  * sync       -> process inline during the request
  * background -> FastAPI BackgroundTasks (own session, processes after response)
  * kafka      -> publish a message; the Kafka worker processes it
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.services import cache
from app.services.chunking import chunk_text
from app.services.embeddings import get_embedding_provider

logger = get_logger(__name__)


async def create_document(
    session: AsyncSession,
    owner_id: int,
    title: str,
    text: str,
    source: str | None = None,
) -> Document:
    """Persist a new document record with status='pending'."""
    doc = Document(
        owner_id=owner_id,
        title=title,
        content=text,
        source=source,
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    await cache.set_job_status(doc.id, "pending")
    return doc


async def process_document(document_id: int) -> int:
    """Chunk + embed + store chunks for a document. Opens its own session.

    Returns the number of chunks created. Safe to call from a background task,
    a Kafka consumer, or inline.
    """
    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            logger.warning("process_document: document %s not found", document_id)
            return 0

        doc.status = "processing"
        doc.error = None
        await session.commit()
        await cache.set_job_status(document_id, "processing")

        try:
            # Remove any pre-existing chunks (idempotent re-processing).
            await session.execute(delete(Chunk).where(Chunk.document_id == document_id))

            chunks = chunk_text(doc.content)
            if not chunks:
                doc.status = "completed"
                await session.commit()
                await cache.set_job_status(document_id, "completed", chunks=0)
                return 0

            provider = get_embedding_provider()
            embeddings = await provider.embed_documents([c.content for c in chunks])

            for tc, vector in zip(chunks, embeddings):
                session.add(
                    Chunk(
                        document_id=document_id,
                        chunk_index=tc.index,
                        content=tc.content,
                        token_count=tc.token_count,
                        embedding=vector,
                    )
                )

            doc.status = "completed"
            await session.commit()
            await cache.set_job_status(document_id, "completed", chunks=len(chunks))
            logger.info(
                "Processed document %s: %d chunks embedded.", document_id, len(chunks)
            )
            return len(chunks)

        except Exception as exc:  # noqa: BLE001 - record failure, don't crash worker
            await session.rollback()
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                doc.error = str(exc)
                await session.commit()
            await cache.set_job_status(document_id, "failed", error=str(exc))
            logger.exception("Failed to process document %s", document_id)
            raise


async def count_chunks(session: AsyncSession, document_id: int) -> int:
    result = await session.execute(
        select(Chunk.id).where(Chunk.document_id == document_id)
    )
    return len(result.scalars().all())
