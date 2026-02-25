import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

sys.path.insert(0, "/app/shared")

from app.consumer import start_consumer, stop_consumer
from app.solvers import solve_request, SchedulingSolver, ResourceAllocator


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SolverRequest(BaseModel):
    plan_id: uuid.UUID
    solver_type: str
    constraints: dict[str, Any]
    objective: str
    parameters: dict[str, Any] | None = None


class SolverResult(BaseModel):
    result_id: uuid.UUID
    plan_id: uuid.UUID
    solver_type: str
    status: str
    objective: str
    result: dict[str, Any] | None = None
    created_at: str


class ScheduleTask(BaseModel):
    id: str
    duration: float
    dependencies: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class ScheduleRequest(BaseModel):
    tasks: list[ScheduleTask]


class AllocateRequest(BaseModel):
    resources: list[dict[str, Any]]
    demands: list[dict[str, Any]]
    constraints: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory results store
# ---------------------------------------------------------------------------

_results: dict[uuid.UUID, SolverResult] = {}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_consumer()
    yield
    await stop_consumer()


app = FastAPI(
    title="Solver Engine",
    description="Constraint satisfaction and optimization for construction scheduling, resource allocation, and plan optimization.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/solve", response_model=SolverResult)
async def submit_solver_request(req: SolverRequest):
    """Submit a solver request and return the result."""
    plan_data = req.constraints  # constraints carry the plan data context
    result_data = solve_request(
        solver_type=req.solver_type,
        plan_data=plan_data,
        constraints=req.constraints,
        objective=req.objective,
        parameters=req.parameters,
    )

    solver_result = SolverResult(
        result_id=uuid.uuid4(),
        plan_id=req.plan_id,
        solver_type=req.solver_type,
        status="completed",
        objective=req.objective,
        result=result_data,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _results[solver_result.result_id] = solver_result
    return solver_result


@app.get("/solve/{result_id}", response_model=SolverResult)
async def get_solver_result(result_id: uuid.UUID):
    """Retrieve a solver result by its ID."""
    if result_id not in _results:
        raise HTTPException(status_code=404, detail="Solver result not found")
    return _results[result_id]


@app.get("/solve", response_model=list[SolverResult])
async def list_solver_results(
    solver_type: str | None = Query(default=None),
    plan_id: uuid.UUID | None = Query(default=None),
):
    """List solver results with optional filters."""
    results = list(_results.values())
    if solver_type is not None:
        results = [r for r in results if r.solver_type == solver_type]
    if plan_id is not None:
        results = [r for r in results if r.plan_id == plan_id]
    return results


@app.post("/solve/schedule")
async def solve_schedule(req: ScheduleRequest):
    """Specialized scheduling endpoint."""
    tasks = [t.model_dump() for t in req.tasks]
    solver = SchedulingSolver()
    schedule = solver.solve(tasks, constraints={})
    return schedule


@app.post("/solve/allocate")
async def solve_allocate(req: AllocateRequest):
    """Resource allocation endpoint."""
    allocator = ResourceAllocator()
    allocation = allocator.allocate(req.resources, req.demands, req.constraints)
    return allocation


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "solver-engine"}
