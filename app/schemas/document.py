"""Document ingestion request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, description="Raw document text to ingest.")
    source: Optional[str] = Field(default=None, max_length=512)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: Optional[str]
    status: str
    error: Optional[str] = None
    created_at: datetime


class IngestResponse(BaseModel):
    document: DocumentResponse
    chunks_created: int = 0
    mode: str
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
