"""API tests for the Belief State Engine service."""

import sys
import os
from uuid import uuid4

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "belief-state-engine"))
sys.path.insert(0, SERVICES_DIR)


class TestCreateBelief:
    """Tests for POST /beliefs."""

    @pytest.mark.asyncio
    async def test_create_belief_returns_201(self, belief_state_client):
        response = await belief_state_client.post(
            "/beliefs",
            json={
                "entity_type": "task",
                "entity_id": "task-001",
                "belief_vector": {"on_schedule": 0.8, "within_budget": 0.7},
                "confidence": 0.75,
                "evidence": {"source": "sensor", "strength": 0.8},
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["entity_type"] == "task"
        assert body["entity_id"] == "task-001"
        assert body["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_create_belief_without_evidence(self, belief_state_client):
        response = await belief_state_client.post(
            "/beliefs",
            json={
                "entity_type": "resource",
                "entity_id": "crane-01",
                "belief_vector": {"available": 1.0},
                "confidence": 0.9,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_create_belief_invalid_confidence(self, belief_state_client):
        """Confidence outside [0, 1] should fail validation."""
        response = await belief_state_client.post(
            "/beliefs",
            json={
                "entity_type": "task",
                "entity_id": "bad",
                "belief_vector": {},
                "confidence": 1.5,
            },
        )

        assert response.status_code == 422


class TestGetBelief:
    """Tests for GET /beliefs/{entity_type}/{entity_id}."""

    @pytest.mark.asyncio
    async def test_retrieve_existing_belief(self, belief_state_client):
        # Create first
        await belief_state_client.post(
            "/beliefs",
            json={
                "entity_type": "project",
                "entity_id": "proj-get-test",
                "belief_vector": {"status": 0.5},
                "confidence": 0.6,
            },
        )

        # Retrieve
        response = await belief_state_client.get("/beliefs/project/proj-get-test")

        assert response.status_code == 200
        body = response.json()
        assert body["entity_type"] == "project"
        assert body["entity_id"] == "proj-get-test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_belief_returns_404(self, belief_state_client):
        response = await belief_state_client.get("/beliefs/task/does-not-exist")

        assert response.status_code == 404


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, belief_state_client):
        response = await belief_state_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "belief-state-engine"
