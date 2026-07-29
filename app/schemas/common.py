"""Shared response schemas."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
