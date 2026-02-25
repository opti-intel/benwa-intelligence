"""Ingestion Gateway - FastAPI service for raw data ingestion."""

import sys
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Add shared library to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.schemas import IngestionRecord, KafkaEvent
from shared.kafka_utils import get_kafka_producer, publish_event
from shared.db import get_db

from .parser import normalize_payload

# ---------------------------------------------------------------------------
# In-memory store (swap for real Postgres queries once DB migrations are in)
# ---------------------------------------------------------------------------
_records: dict[UUID, IngestionRecord] = {}
_kafka_producer = None


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks for the Kafka producer."""
    global _kafka_producer
    try:
        _kafka_producer = await get_kafka_producer()
    except Exception:
        _kafka_producer = None  # allow service to run without Kafka for dev
    yield
    if _kafka_producer is not None:
        await _kafka_producer.stop()


app = FastAPI(
    title="Ingestion Gateway",
    description="Accepts raw construction data and publishes to the ingestion pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    source_type: str
    source_uri: Optional[str] = None
    raw_payload: dict


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/ingest", response_model=IngestionRecord, status_code=201)
async def ingest(request: IngestRequest):
    """Accept a raw payload, persist it, and publish a Kafka event."""
    normalized = normalize_payload(request.source_type, request.raw_payload)

    record = IngestionRecord(
        source_type=request.source_type,
        source_uri=request.source_uri,
        raw_payload=request.raw_payload,
        normalized_payload=normalized,
        status="ingested",
    )

    # Persist (in-memory for now)
    _records[record.id] = record

    # Publish Kafka event
    if _kafka_producer is not None:
        event = KafkaEvent(
            event_type="raw_ingestion",
            payload=record.model_dump(mode="json"),
            source_service="ingestion-gateway",
        )
        try:
            await publish_event(_kafka_producer, "raw-ingestion", event)
        except Exception:
            record.status = "kafka_publish_failed"

    return record


@app.get("/ingest/{record_id}", response_model=IngestionRecord)
async def get_record(record_id: UUID):
    """Retrieve a single ingestion record by ID."""
    record = _records.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@app.get("/ingest", response_model=list[IngestionRecord])
async def list_records(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List recent ingestion records with pagination."""
    all_records = sorted(_records.values(), key=lambda r: r.created_at, reverse=True)
    return all_records[offset : offset + limit]


@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "ingestion-gateway"}
