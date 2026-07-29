"""Redis-backed cache and ingestion job-status store.

All operations degrade gracefully: if Redis is unavailable the app keeps
working (cache misses / no-op status updates) instead of failing requests.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _client


async def cache_get(key: str) -> Optional[Any]:
    try:
        raw = await get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001 - cache must never break requests
        logger.warning("cache_get failed for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    try:
        await get_redis().set(
            key, json.dumps(value), ex=ttl or settings.CACHE_TTL_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_set failed for %s: %s", key, exc)


async def set_job_status(document_id: int, status: str, **extra: Any) -> None:
    payload = {"document_id": document_id, "status": status, **extra}
    await cache_set(f"ingest:status:{document_id}", payload, ttl=86400)


async def get_job_status(document_id: int) -> Optional[dict[str, Any]]:
    return await cache_get(f"ingest:status:{document_id}")


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # noqa: BLE001
            pass
        _client = None
