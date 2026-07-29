"""Kafka ingestion worker.

Consumes ``document.ingest`` events and runs the chunk + embed + store pipeline
for each document. Run as a standalone process:

    python -m app.workers.kafka_consumer
"""
from __future__ import annotations

import asyncio
import json
import signal

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ingestion import process_document

logger = get_logger(__name__)


async def consume() -> None:
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        settings.KAFKA_INGEST_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info(
        "Kafka ingestion worker listening on topic '%s' (%s)",
        settings.KAFKA_INGEST_TOPIC,
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )

    stop = asyncio.Event()

    def _request_stop(*_: object) -> None:
        logger.info("Shutdown signal received; stopping worker...")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Signal handlers are not available on Windows event loops.
            pass

    try:
        async for msg in consumer:
            if stop.is_set():
                break
            document_id = msg.value.get("document_id")
            if document_id is None:
                logger.warning("Received message without document_id: %s", msg.value)
                continue
            try:
                await process_document(int(document_id))
            except Exception:  # noqa: BLE001 - keep the worker alive on failures
                logger.exception("Error processing document %s", document_id)
    finally:
        await consumer.stop()
        logger.info("Kafka ingestion worker stopped.")


def main() -> None:
    asyncio.run(consume())


if __name__ == "__main__":
    main()
