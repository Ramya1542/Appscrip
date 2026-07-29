"""RAG chat endpoint: retrieve relevant chunks + answer with an LLM."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, RetrievedChunk
from app.services import cache
from app.services.llm import generate_answer, stream_answer
from app.services.retrieval import ScoredChunk, retrieve_relevant_chunks

router = APIRouter(tags=["chat"])


def _cache_key(user_id: int, req: ChatRequest, top_k: int) -> str:
    raw = json.dumps(
        {
            "u": user_id,
            "q": req.query,
            "k": top_k,
            "doc": req.document_id,
            "model": settings.LLM_MODEL,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"chat:answer:{digest}"


def _to_schema(chunks: list[ScoredChunk]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            content=c.content,
            score=round(c.score, 6),
        )
        for c in chunks
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    top_k = payload.top_k or settings.RETRIEVAL_TOP_K

    chunks = await retrieve_relevant_chunks(
        session,
        query=payload.query,
        owner_id=current_user.id,
        top_k=top_k,
        document_id=payload.document_id,
    )
    sources = _to_schema(chunks)

    # ---- Streaming response (Server-Sent Events) ----
    if payload.stream:

        async def event_generator():
            # Emit the retrieved sources first so the client can render citations.
            yield f"event: sources\ndata: {json.dumps([s.model_dump() for s in sources])}\n\n"
            async for token in stream_answer(payload.query, chunks):
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ---- Non-streaming: check cache, then call the LLM ----
    key = _cache_key(current_user.id, payload, top_k)
    cached = await cache.cache_get(key)
    if cached is not None:
        return ChatResponse(
            query=payload.query,
            answer=cached["answer"],
            sources=sources,
            cached=True,
        )

    answer = await generate_answer(payload.query, chunks)
    await cache.cache_set(key, {"answer": answer})

    return ChatResponse(
        query=payload.query, answer=answer, sources=sources, cached=False
    )
