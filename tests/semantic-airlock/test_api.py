"""API tests for the Semantic Airlock service."""

import sys
import os
from uuid import uuid4

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "semantic-airlock"))
sys.path.insert(0, SERVICES_DIR)


class TestValidateEndpoint:
    """Tests for POST /validate."""

    @pytest.mark.asyncio
    async def test_valid_plan_returns_200(self, semantic_airlock_client, sample_valid_plan):
        response = await semantic_airlock_client.post(
            "/validate",
            json={
                "plan_data": sample_valid_plan,
                "plan_name": "Foundation Phase 1",
                "project_id": str(uuid4()),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "validation_id" in body
        assert body["plan_name"] == "Foundation Phase 1"
        assert body["overall_passed"] is True
        assert len(body["results"]) == 3

    @pytest.mark.asyncio
    async def test_invalid_plan_missing_safety(self, semantic_airlock_client, sample_invalid_plan):
        response = await semantic_airlock_client.post(
            "/validate",
            json={
                "plan_data": sample_invalid_plan,
                "plan_name": "Incomplete Plan",
                "project_id": str(uuid4()),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["overall_passed"] is False

        # Find the safety result and verify it failed
        safety_results = [r for r in body["results"] if r["validator"] == "safety"]
        assert len(safety_results) == 1
        assert safety_results[0]["passed"] is False
        assert len(safety_results[0]["issues"]) > 0

    @pytest.mark.asyncio
    async def test_empty_plan_data(self, semantic_airlock_client):
        response = await semantic_airlock_client.post(
            "/validate",
            json={
                "plan_data": {},
                "plan_name": "Empty",
                "project_id": str(uuid4()),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["overall_passed"] is False

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, semantic_airlock_client):
        """Omitting plan_name should trigger a Pydantic validation error."""
        response = await semantic_airlock_client.post(
            "/validate",
            json={"plan_data": {"description": "test"}},
        )

        assert response.status_code == 422


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, semantic_airlock_client):
        response = await semantic_airlock_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "semantic-airlock"
