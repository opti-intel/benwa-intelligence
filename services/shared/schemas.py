"""Shared Pydantic v2 schemas used across benwa-intelligence services."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IngestionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_type: str
    source_uri: Optional[str] = None
    raw_payload: dict
    normalized_payload: Optional[dict] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    ingestion_id: UUID
    validation_type: str
    passed: bool
    confidence: Optional[float] = None
    findings: Optional[dict] = None
    ai_reasoning: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConstructionPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    plan_name: str
    plan_version: int = 1
    plan_data: dict
    status: str = "draft"
    semantic_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BeliefState(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    entity_type: str
    entity_id: str
    belief_vector: dict
    confidence: float
    evidence: Optional[dict] = None
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SolverRequest(BaseModel):
    plan_id: UUID
    solver_type: str
    constraints: dict
    objective: str
    parameters: Optional[dict] = None


class SolverResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    solver_type: str
    objective_value: Optional[float] = None
    constraints_satisfied: int = 0
    constraints_total: int = 0
    solution: dict
    metadata: Optional[dict] = None
    compute_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: Optional[str] = None
    metadata: Optional[dict] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KafkaEvent(BaseModel):
    event_type: str
    payload: dict
    source_service: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: UUID = Field(default_factory=uuid4)
