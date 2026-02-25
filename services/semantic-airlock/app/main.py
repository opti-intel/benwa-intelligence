import sys
import os
import asyncio
import logging
from uuid import UUID, uuid4
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Add shared lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from app.validators import run_all_validators
from app.consumer import consume_raw_ingestion
from app.nl_parser import parse_bericht

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Semantic Airlock",
    description="Validates and gates AI-generated construction plans before they enter the system.",
    version="0.1.0",
)

# In-memory store for validation results
_validation_store: dict[str, dict] = {}


class PlanRequest(BaseModel):
    plan_data: dict[str, Any]
    plan_name: str
    project_id: UUID


class ValidationResult(BaseModel):
    validation_id: str = Field(default_factory=lambda: str(uuid4()))
    validator: str
    passed: bool
    issues: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class ValidationResponse(BaseModel):
    validation_id: str
    plan_name: str
    project_id: UUID
    results: list[ValidationResult]
    overall_passed: bool


class BatchPlanRequest(BaseModel):
    plans: list[PlanRequest]


class BatchValidationResponse(BaseModel):
    responses: list[ValidationResponse]


@app.post("/validate", response_model=ValidationResponse)
async def validate_plan(request: PlanRequest) -> ValidationResponse:
    """Validate a single construction plan through safety, compliance, and semantic checks."""
    validation_id = str(uuid4())
    raw_results = await run_all_validators(request.plan_data)

    results = [
        ValidationResult(
            validation_id=validation_id,
            validator=r["validator"],
            passed=r["passed"],
            issues=r.get("issues", []),
            reasoning=r.get("reasoning"),
        )
        for r in raw_results
    ]

    overall_passed = all(r.passed for r in results)

    response = ValidationResponse(
        validation_id=validation_id,
        plan_name=request.plan_name,
        project_id=request.project_id,
        results=results,
        overall_passed=overall_passed,
    )

    _validation_store[validation_id] = response.model_dump()
    return response


@app.post("/validate/batch", response_model=BatchValidationResponse)
async def validate_batch(request: BatchPlanRequest) -> BatchValidationResponse:
    """Batch validate multiple construction plans."""
    responses: list[ValidationResponse] = []
    for plan in request.plans:
        result = await validate_plan(plan)
        responses.append(result)
    return BatchValidationResponse(responses=responses)


@app.get("/validations/{validation_id}", response_model=ValidationResponse)
async def get_validation(validation_id: str) -> ValidationResponse:
    """Retrieve a stored validation result by ID."""
    stored = _validation_store.get(validation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Validation result not found")
    return ValidationResponse(**stored)


class ChatRequest(BaseModel):
    message: str
    project_id: UUID
    context: dict[str, Any] | None = None  # Partial task context from previous turn


class ExtractedTask(BaseModel):
    naam: str
    beschrijving: str
    startdatum: str | None = None
    einddatum: str | None = None
    toegewezen_aan: str = ""
    locatie: str = ""
    taak_type: str = ""


class ChatResponse(BaseModel):
    antwoord: str
    taak: ExtractedTask | None = None
    heeft_taak: bool = False
    onvolledig: dict[str, Any] | None = None  # Partial context for follow-up


@app.post("/chat", response_model=ChatResponse)
async def chat_message(request: ChatRequest) -> ChatResponse:
    """Parse a Dutch construction chat message using rule-based NLP (no external API).
    Supports multi-turn: pass `context` from previous response's `onvolledig` to continue."""
    try:
        result = parse_bericht(request.message, context=request.context)

        taak = None
        if result["heeft_taak"] and result["taak"]:
            t = result["taak"]
            taak = ExtractedTask(
                naam=t["naam"],
                beschrijving=t["beschrijving"],
                startdatum=t.get("startdatum"),
                einddatum=t.get("einddatum"),
                toegewezen_aan=t.get("toegewezen_aan", ""),
                locatie=t.get("locatie", ""),
                taak_type=t.get("taak_type", ""),
            )

        return ChatResponse(
            antwoord=result["antwoord"],
            taak=taak,
            heeft_taak=result["heeft_taak"],
            onvolledig=result.get("onvolledig"),
        )

    except Exception as exc:
        logger.exception("Chat endpoint error")
        return ChatResponse(
            antwoord=f"Er ging iets mis bij het verwerken: {exc}",
            taak=None,
            heeft_taak=False,
            onvolledig=None,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "semantic-airlock"}


@app.on_event("startup")
async def startup_event() -> None:
    """Start background Kafka consumer on startup."""
    asyncio.create_task(consume_raw_ingestion())
