"""Kafka producer for document-ingestion events.

Lazily starts a shared AIOKafkaProducer. Publishing degrades gracefully:
if Kafka is unreachable, ``publish_ingest_event`` returns False so the caller
can fall back to another ingestion strategy.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_producer = None


async def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    _producer = producer
    logger.info("Kafka producer connected to %s", settings.KAFKA_BOOTSTRAP_SERVERS)
    return _producer


async def publish_ingest_event(document_id: int) -> bool:
    try:
        producer = await _get_producer()
        await producer.send_and_wait(
            settings.KAFKA_INGEST_TOPIC, {"document_id": document_id}
        )
        logger.info("Published ingest event for document %s", document_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish ingest event for %s: %s", document_id, exc)
        return False


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        except Exception:  # noqa: BLE001
            pass
        _producer = None
