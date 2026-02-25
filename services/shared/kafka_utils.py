"""Kafka producer/consumer helpers using aiokafka."""

import json
from datetime import datetime
from uuid import UUID

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import get_settings
from .schemas import KafkaEvent


def _json_serializer(obj):
    """Custom JSON serializer for objects not handled by default json encoder."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def get_kafka_producer() -> AIOKafkaProducer:
    """Create and return an AIOKafkaProducer instance."""
    settings = get_settings()
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=_json_serializer).encode("utf-8"),
    )
    await producer.start()
    return producer


async def get_kafka_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    """Create and return an AIOKafkaConsumer instance for the given topic and group."""
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    return consumer


async def publish_event(producer: AIOKafkaProducer, topic: str, event: KafkaEvent) -> None:
    """Serialize a KafkaEvent and publish it to the specified topic."""
    await producer.send_and_wait(topic, value=event.model_dump())
