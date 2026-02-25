"""API tests for the Solver Engine service."""

import sys
import os
from uuid import uuid4
from unittest.mock import patch, AsyncMock

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "solver-engine"))
sys.path.insert(0, SERVICES_DIR)


class TestSolveEndpoint:
    """Tests for POST /solve."""

    @pytest.mark.asyncio
    async def test_solve_schedule(self, solver_engine_client):
        plan_id = str(uuid4())
        response = await solver_engine_client.post(
            "/solve",
            json={
                "plan_id": plan_id,
                "solver_type": "schedule",
                "constraints": {
                    "tasks": [
                        {"id": "a", "duration": 2.0, "dependencies": []},
                        {"id": "b", "duration": 3.0, "dependencies": ["a"]},
                    ]
                },
                "objective": "minimize_makespan",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["solver_type"] == "schedule"
        assert body["status"] == "completed"
        assert body["result"]["makespan"] == 5.0

    @pytest.mark.asyncio
    async def test_solve_allocate(self, solver_engine_client):
        plan_id = str(uuid4())
        response = await solver_engine_client.post(
            "/solve",
            json={
                "plan_id": plan_id,
                "solver_type": "allocate",
                "constraints": {
                    "resources": [{"id": "r1", "capacity": 100}],
                    "demands": [{"id": "d1", "required_capacity": 50, "priority": 5}],
                },
                "objective": "maximize_utilization",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["solver_type"] == "allocate"
        assert body["result"]["unmet_demands"] == []

    @pytest.mark.asyncio
    async def test_solve_unknown_solver_type(self, solver_engine_client):
        response = await solver_engine_client.post(
            "/solve",
            json={
                "plan_id": str(uuid4()),
                "solver_type": "unknown",
                "constraints": {},
                "objective": "test",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "error" in body["result"]

    @pytest.mark.asyncio
    async def test_solve_missing_fields_returns_422(self, solver_engine_client):
        response = await solver_engine_client.post(
            "/solve",
            json={"plan_id": str(uuid4())},
        )

        assert response.status_code == 422


class TestScheduleEndpoint:
    """Tests for POST /solve/schedule."""

    @pytest.mark.asyncio
    async def test_schedule_with_tasks(self, solver_engine_client, sample_tasks):
        response = await solver_engine_client.post(
            "/solve/schedule",
            json={"tasks": sample_tasks},
        )

        assert response.status_code == 200
        body = response.json()
        assert "schedule" in body
        assert "makespan" in body
        assert body["makespan"] == 15.0

    @pytest.mark.asyncio
    async def test_schedule_empty_tasks(self, solver_engine_client):
        response = await solver_engine_client.post(
            "/solve/schedule",
            json={"tasks": []},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["makespan"] == 0.0


class TestAllocateEndpoint:
    """Tests for POST /solve/allocate."""

    @pytest.mark.asyncio
    async def test_allocate_resources(self, solver_engine_client, sample_resources, sample_demands):
        response = await solver_engine_client.post(
            "/solve/allocate",
            json={
                "resources": sample_resources,
                "demands": sample_demands,
                "constraints": {},
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "allocations" in body
        assert body["unmet_demands"] == []

    @pytest.mark.asyncio
    async def test_allocate_insufficient_resources(self, solver_engine_client):
        response = await solver_engine_client.post(
            "/solve/allocate",
            json={
                "resources": [{"id": "tiny", "capacity": 5}],
                "demands": [{"id": "big", "required_capacity": 100, "priority": 1}],
                "constraints": {},
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "big" in body["unmet_demands"]


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, solver_engine_client):
        response = await solver_engine_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "solver-engine"
