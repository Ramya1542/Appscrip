"""Document ingestion endpoints."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.models.document import Document
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    IngestRequest,
    IngestResponse,
)
from app.services import cache
from app.services.ingestion import (
    count_chunks,
    create_document,
    process_document,
)
from app.workers.kafka_producer import publish_ingest_event

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    """Ingest a text document: store it, then chunk + embed + store the chunks.

    Processing strategy is controlled by INGEST_MODE (sync|background|kafka).
    """
    doc = await create_document(
        session,
        owner_id=current_user.id,
        title=payload.title,
        text=payload.text,
        source=payload.source,
    )

    mode = settings.INGEST_MODE
    chunks_created = 0

    if mode == "sync":
        chunks_created = await process_document(doc.id)
        message = "Document ingested and processed synchronously."
    elif mode == "kafka":
        published = await publish_ingest_event(doc.id)
        if published:
            message = "Document queued for processing via Kafka."
        else:
            # Fallback so ingestion still works if Kafka is unreachable.
            logger.warning("Kafka publish failed; processing in background instead.")
            background_tasks.add_task(process_document, doc.id)
            message = "Kafka unavailable; document queued as a background task."
    else:  # background (default)
        background_tasks.add_task(process_document, doc.id)
        message = "Document accepted; processing in the background."

    # Reload to reflect any status change from sync processing.
    await session.refresh(doc)

    return IngestResponse(
        document=DocumentResponse.model_validate(doc),
        chunks_created=chunks_created,
        mode=mode,
        message=message,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    result = await session.execute(
        select(Document)
        .where(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    doc = await session.get(Document, document_id)
    if doc is None or doc.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Poll ingestion progress (from Redis job status, falling back to the DB)."""
    doc = await session.get(Document, document_id)
    if doc is None or doc.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    status_payload = await cache.get_job_status(document_id)
    chunks = await count_chunks(session, document_id)
    return {
        "document_id": document_id,
        "status": doc.status,
        "error": doc.error,
        "chunks": chunks,
        "cached_status": status_payload,
    }
