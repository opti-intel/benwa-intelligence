from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.solvers import solve_request

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REQUEST_TOPIC = "solver-requests"
RESULT_TOPIC = "solver-results"

_consumer: AIOKafkaConsumer | None = None
_producer: AIOKafkaProducer | None = None
_task: asyncio.Task | None = None


async def _consume_loop() -> None:
    """Continuously consume solver-requests, run the solver, publish results."""
    global _consumer, _producer

    _consumer = AIOKafkaConsumer(
        REQUEST_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="solver-engine",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    _producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    try:
        await _consumer.start()
        await _producer.start()
        logger.info("Kafka consumer started on topic '%s'", REQUEST_TOPIC)

        async for msg in _consumer:
            try:
                data = msg.value
                solver_type = data.get("solver_type", "")
                plan_data = data.get("constraints", {})
                constraints = data.get("constraints", {})
                objective = data.get("objective", "")
                parameters = data.get("parameters")

                result_data = solve_request(
                    solver_type=solver_type,
                    plan_data=plan_data,
                    constraints=constraints,
                    objective=objective,
                    parameters=parameters,
                )

                result_msg = {
                    "result_id": str(uuid.uuid4()),
                    "plan_id": data.get("plan_id"),
                    "solver_type": solver_type,
                    "status": "completed",
                    "objective": objective,
                    "result": result_data,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                await _producer.send_and_wait(RESULT_TOPIC, result_msg)
                logger.info("Published result %s to '%s'", result_msg["result_id"], RESULT_TOPIC)
            except Exception:
                logger.exception("Error processing solver request")
    finally:
        await _consumer.stop()
        await _producer.stop()


async def start_consumer() -> None:
    """Start the Kafka consumer background task."""
    global _task
    try:
        _task = asyncio.create_task(_consume_loop())
        logger.info("Solver-engine Kafka consumer task created")
    except Exception:
        logger.warning("Could not start Kafka consumer — running without it")


async def stop_consumer() -> None:
    """Stop the Kafka consumer background task."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.info("Solver-engine Kafka consumer task stopped")
