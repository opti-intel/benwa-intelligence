"""Kafka consumer for the Belief State Engine.

Consumes from 'validated-plans' and 'belief-updates' topics, updates belief
states based on incoming events, and publishes belief change notifications.
"""

import asyncio
import json
import logging
import sys
import os

from aiokafka import AIOKafkaConsumer

# Add shared library to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.config import get_settings
from shared.kafka_utils import get_kafka_producer, publish_event
from shared.schemas import BeliefState, KafkaEvent

from .belief_engine import BeliefEngine
from .graph import get_neo4j_driver

logger = logging.getLogger(__name__)

# Topics this consumer subscribes to
CONSUME_TOPICS = ["validated-plans", "belief-updates"]
CONSUMER_GROUP = "belief-state-engine"

# Topic to publish belief change events to
PUBLISH_TOPIC = "belief-changes"


async def handle_validated_plan(payload: dict, engine: BeliefEngine) -> dict | None:
    """
    Handle an event from the 'validated-plans' topic.

    Extracts plan validation results and updates the corresponding belief state.
    """
    plan_id = payload.get("plan_id") or payload.get("id")
    if plan_id is None:
        logger.warning("Validated plan event missing plan_id, skipping")
        return None

    confidence = payload.get("confidence", 0.5)
    validation_passed = payload.get("passed", True)

    evidence = {
        "source": "validated-plans",
        "strength": confidence if validation_passed else 1.0 - confidence,
        "validation_passed": validation_passed,
        "findings": payload.get("findings"),
    }

    updated_confidence = engine.update_belief(
        entity_type="ConstructionPlan",
        entity_id=str(plan_id),
        new_evidence=evidence,
        prior_confidence=confidence,
    )

    belief = BeliefState(
        entity_type="ConstructionPlan",
        entity_id=str(plan_id),
        belief_vector={"validation_status": "passed" if validation_passed else "failed"},
        confidence=updated_confidence,
        evidence=evidence,
    )

    return belief.model_dump(mode="json")


async def handle_belief_update(payload: dict, engine: BeliefEngine) -> dict | None:
    """
    Handle an event from the 'belief-updates' topic.

    Applies an external belief update and optionally triggers propagation.
    """
    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")

    if entity_type is None or entity_id is None:
        logger.warning("Belief update event missing entity_type or entity_id, skipping")
        return None

    prior_confidence = payload.get("confidence", 0.5)
    evidence = payload.get("evidence", {})

    updated_confidence = engine.update_belief(
        entity_type=entity_type,
        entity_id=entity_id,
        new_evidence=evidence,
        prior_confidence=prior_confidence,
    )

    # Propagate if requested
    should_propagate = payload.get("propagate", False)
    propagation_results = []
    if should_propagate:
        propagation_results = engine.propagate_beliefs(
            entity_type=entity_type,
            entity_id=entity_id,
        )

    belief = BeliefState(
        entity_type=entity_type,
        entity_id=entity_id,
        belief_vector=payload.get("belief_vector", {}),
        confidence=updated_confidence,
        evidence=evidence,
    )

    result = belief.model_dump(mode="json")
    result["propagation"] = propagation_results
    return result


async def run_consumer() -> None:
    """
    Main consumer loop.

    Connects to Kafka, consumes from the configured topics, routes messages
    to the appropriate handler, and publishes belief change events.
    """
    settings = get_settings()

    # Initialize Neo4j and belief engine
    driver = get_neo4j_driver()
    engine = BeliefEngine(driver)

    # Initialize Kafka producer for publishing belief changes
    producer = await get_kafka_producer()

    # Initialize Kafka consumer
    consumer = AIOKafkaConsumer(
        *CONSUME_TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()

    logger.info("Belief state engine consumer started, listening on: %s", CONSUME_TOPICS)

    try:
        async for message in consumer:
            topic = message.topic
            payload = message.value

            logger.info("Received message on topic=%s partition=%s offset=%s", topic, message.partition, message.offset)

            try:
                result = None
                if topic == "validated-plans":
                    result = await handle_validated_plan(payload, engine)
                elif topic == "belief-updates":
                    result = await handle_belief_update(payload, engine)

                if result is not None:
                    event = KafkaEvent(
                        event_type="belief_changed",
                        payload=result,
                        source_service="belief-state-engine",
                    )
                    await publish_event(producer, PUBLISH_TOPIC, event)
                    logger.info("Published belief change event for %s", result.get("entity_id", "unknown"))

            except Exception:
                logger.exception("Error processing message from topic=%s", topic)

    finally:
        await consumer.stop()
        await producer.stop()
        driver.close()
        logger.info("Belief state engine consumer stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_consumer())
