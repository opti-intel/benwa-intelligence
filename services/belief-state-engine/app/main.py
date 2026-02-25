"""Belief State Engine - Maintains probabilistic belief states about construction projects."""

import sys
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Add shared library to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.schemas import BeliefState, KafkaEvent
from shared.kafka_utils import get_kafka_producer, publish_event

from .belief_engine import BeliefEngine
from .graph import Neo4jClient, get_neo4j_driver

# ---------------------------------------------------------------------------
# In-memory store (swap for real Postgres queries once DB migrations are in)
# ---------------------------------------------------------------------------
_beliefs: dict[str, BeliefState] = {}  # keyed by "{entity_type}:{entity_id}"
_kafka_producer = None
_neo4j_client: Optional[Neo4jClient] = None
_belief_engine: Optional[BeliefEngine] = None


def _belief_key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks for Kafka producer and Neo4j driver."""
    global _kafka_producer, _neo4j_client, _belief_engine

    # Kafka
    try:
        _kafka_producer = await get_kafka_producer()
    except Exception:
        _kafka_producer = None

    # Neo4j
    try:
        driver = get_neo4j_driver()
        _neo4j_client = Neo4jClient(driver)
        _belief_engine = BeliefEngine(driver)
    except Exception:
        _neo4j_client = None
        _belief_engine = None

    yield

    if _kafka_producer is not None:
        await _kafka_producer.stop()
    if _neo4j_client is not None:
        _neo4j_client.close()


app = FastAPI(
    title="Belief State Engine",
    description="Maintains probabilistic belief states about construction project status, resource availability, and risk factors.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class CreateBeliefRequest(BaseModel):
    entity_type: str
    entity_id: str
    belief_vector: dict
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[dict] = None


class PropagateRequest(BaseModel):
    entity_type: str
    entity_id: str


class CreateRelationshipRequest(BaseModel):
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    rel_type: str
    properties: Optional[dict] = None


class PropagationResult(BaseModel):
    source: str
    updated_count: int
    updates: list[dict]


# ---------------------------------------------------------------------------
# Routes - Beliefs
# ---------------------------------------------------------------------------
@app.post("/beliefs", response_model=BeliefState, status_code=201)
async def create_or_update_belief(request: CreateBeliefRequest):
    """Create or update a belief state for a given entity."""
    key = _belief_key(request.entity_type, request.entity_id)
    existing = _beliefs.get(key)

    # If a prior belief exists, run a Bayesian update via the engine
    if existing is not None and _belief_engine is not None:
        updated_confidence = _belief_engine.update_belief(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            new_evidence=request.evidence or {},
            prior_confidence=existing.confidence,
        )
    else:
        updated_confidence = request.confidence

    belief = BeliefState(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        belief_vector=request.belief_vector,
        confidence=updated_confidence,
        evidence=request.evidence,
    )
    _beliefs[key] = belief

    # Publish Kafka event
    if _kafka_producer is not None:
        event = KafkaEvent(
            event_type="belief_updated",
            payload=belief.model_dump(mode="json"),
            source_service="belief-state-engine",
        )
        try:
            await publish_event(_kafka_producer, "belief-updates", event)
        except Exception:
            pass

    return belief


@app.get("/beliefs/{entity_type}/{entity_id}", response_model=BeliefState)
async def get_belief(entity_type: str, entity_id: str):
    """Retrieve the current belief state for an entity."""
    key = _belief_key(entity_type, entity_id)
    belief = _beliefs.get(key)
    if belief is None:
        raise HTTPException(status_code=404, detail="Belief state not found")
    return belief


@app.get("/beliefs", response_model=list[BeliefState])
async def list_beliefs(
    entity_type: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List belief states with optional filters."""
    results = list(_beliefs.values())

    if entity_type is not None:
        results = [b for b in results if b.entity_type == entity_type]

    if min_confidence is not None:
        results = [b for b in results if b.confidence >= min_confidence]

    results.sort(key=lambda b: b.created_at, reverse=True)
    return results[offset : offset + limit]


# ---------------------------------------------------------------------------
# Routes - Propagation
# ---------------------------------------------------------------------------
@app.post("/beliefs/propagate", response_model=PropagationResult)
async def propagate_beliefs(request: PropagateRequest):
    """Trigger belief propagation through the relationship graph."""
    if _belief_engine is None:
        raise HTTPException(status_code=503, detail="Neo4j not available for propagation")

    key = _belief_key(request.entity_type, request.entity_id)
    source_belief = _beliefs.get(key)
    if source_belief is None:
        raise HTTPException(status_code=404, detail="Source belief state not found")

    updates = _belief_engine.propagate_beliefs(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
    )

    # Apply propagated updates to the in-memory store
    for update in updates:
        neighbor_key = _belief_key(update["entity_type"], update["entity_id"])
        existing = _beliefs.get(neighbor_key)
        if existing is not None:
            existing.confidence = update["propagated_confidence"]
        else:
            _beliefs[neighbor_key] = BeliefState(
                entity_type=update["entity_type"],
                entity_id=update["entity_id"],
                belief_vector=source_belief.belief_vector,
                confidence=update["propagated_confidence"],
                evidence={"propagated_from": key},
            )

    return PropagationResult(
        source=key,
        updated_count=len(updates),
        updates=updates,
    )


# ---------------------------------------------------------------------------
# Routes - Graph
# ---------------------------------------------------------------------------
@app.get("/graph/neighbors/{entity_type}/{entity_id}")
async def get_graph_neighbors(entity_type: str, entity_id: str):
    """Get graph neighbors for an entity from Neo4j."""
    if _neo4j_client is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    neighbors = _neo4j_client.get_neighbors(label=entity_type, entity_id=entity_id)
    return {"entity_type": entity_type, "entity_id": entity_id, "neighbors": neighbors}


@app.post("/graph/relationships", status_code=201)
async def create_relationship(request: CreateRelationshipRequest):
    """Create a relationship between two nodes in Neo4j."""
    if _neo4j_client is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    _neo4j_client.create_relationship(
        from_label=request.from_type,
        from_id=request.from_id,
        to_label=request.to_type,
        to_id=request.to_id,
        rel_type=request.rel_type,
        properties=request.properties or {},
    )
    return {
        "status": "created",
        "from": f"{request.from_type}:{request.from_id}",
        "to": f"{request.to_type}:{request.to_id}",
        "rel_type": request.rel_type,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Simple health check endpoint."""
    neo4j_status = "connected" if _neo4j_client is not None else "disconnected"
    return {
        "status": "ok",
        "service": "belief-state-engine",
        "neo4j": neo4j_status,
    }
