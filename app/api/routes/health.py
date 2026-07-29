"""Health / readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.APP_NAME, version=__version__)
