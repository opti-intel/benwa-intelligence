import json
import os
import asyncio
import logging
from typing import Any

from app.validators import run_all_validators

logger = logging.getLogger("semantic-airlock.consumer")

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
RAW_INGESTION_TOPIC = "raw-ingestion"
VALIDATED_PLANS_TOPIC = "validated-plans"
CONSUMER_GROUP = "semantic-airlock-group"


async def consume_raw_ingestion() -> None:
    """Consume plans from the 'raw-ingestion' Kafka topic, validate them,
    and publish results to the 'validated-plans' topic."""
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    # Brief delay to let the application finish starting up
    await asyncio.sleep(2)

    consumer: Any = None
    producer: Any = None

    while True:
        try:
            consumer = AIOKafkaConsumer(
                RAW_INGESTION_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=CONSUMER_GROUP,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )

            await consumer.start()
            await producer.start()
            logger.info("Kafka consumer started on topic '%s'", RAW_INGESTION_TOPIC)

            async for message in consumer:
                try:
                    plan_data = message.value
                    logger.info(
                        "Received plan from topic '%s' partition=%s offset=%s",
                        message.topic,
                        message.partition,
                        message.offset,
                    )

                    results = await run_all_validators(plan_data)
                    overall_passed = all(r["passed"] for r in results)

                    validated_message = {
                        "plan_data": plan_data,
                        "validation_results": results,
                        "overall_passed": overall_passed,
                        "source_topic": RAW_INGESTION_TOPIC,
                        "source_offset": message.offset,
                    }

                    await producer.send_and_wait(
                        VALIDATED_PLANS_TOPIC, value=validated_message
                    )
                    logger.info(
                        "Published validation result to '%s' (passed=%s)",
                        VALIDATED_PLANS_TOPIC,
                        overall_passed,
                    )
                except Exception as exc:
                    logger.exception(
                        "Error processing message at offset %s: %s",
                        message.offset,
                        exc,
                    )

        except asyncio.CancelledError:
            logger.info("Consumer task cancelled, shutting down.")
            break
        except Exception as exc:
            logger.warning(
                "Kafka connection failed (%s), retrying in 5 seconds...", exc
            )
            await asyncio.sleep(5)
        finally:
            if consumer:
                await consumer.stop()
            if producer:
                await producer.stop()
