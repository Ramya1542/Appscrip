"""Chat (RAG) request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: Optional[int] = Field(
        default=None, ge=1, le=20, description="Number of chunks to retrieve."
    )
    document_id: Optional[int] = Field(
        default=None, description="Restrict retrieval to a single document."
    )
    stream: bool = Field(
        default=False, description="Stream the answer token-by-token (SSE)."
    )


class RetrievedChunk(BaseModel):
    document_id: int
    chunk_index: int
    content: str
    score: float


class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: list[RetrievedChunk]
    cached: bool = False
