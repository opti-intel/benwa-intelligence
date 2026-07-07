"""API tests for the Ingestion Gateway service."""

import sys
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
sys.path.insert(0, SERVICES_DIR)

from app.auth import maak_token


def _auth_headers(rol: str = "medewerker") -> dict:
    """Geldige Authorization-header voor tests (endpoints vereisen inloggen)."""
    token = maak_token({
        "sub": "00000000-0000-0000-0000-000000000001",
        "naam": "Testgebruiker",
        "rol": rol,
        "bedrijf": "Testbedrijf",
    })
    return {"Authorization": f"Bearer {token}"}


class TestAuthVereist:
    """De ingest- en tasks-endpoints mogen NIET zonder login bereikbaar zijn."""

    @pytest.mark.asyncio
    async def test_ingest_zonder_login_geweigerd(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.post(
            "/ingest", json={"source_type": "bim", "raw_payload": {}},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_tasks_zonder_login_geweigerd(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.get("/tasks")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_task_verwijderen_vereist_admin(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.delete(
            "/tasks/00000000-0000-0000-0000-000000000002",
            headers=_auth_headers(rol="medewerker"),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_planning_leegmaken_vereist_admin(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.post(
            "/planning/leegmaken",
            headers=_auth_headers(rol="medewerker"),
            json={"bevestiging": "LEEGMAKEN"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_planning_leegmaken_vereist_bevestigingswoord(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.post(
            "/planning/leegmaken",
            headers=_auth_headers(rol="admin"),
            json={"bevestiging": "verkeerd"},
        )
        assert response.status_code == 422


class TestIngestEndpoint:
    """Tests for POST /ingest."""

    @pytest.mark.asyncio
    async def test_ingest_valid_bim_payload(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.post(
            "/ingest",
            headers=_auth_headers(),
            json={
                "source_type": "bim",
                "source_uri": "s3://models/building-a.ifc",
                "raw_payload": {
                    "elements": [{"type": "wall", "id": "w1"}],
                    "metadata": {"version": "2.0"},
                },
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["source_type"] == "bim"
        assert body["status"] in ("ingested", "kafka_publish_failed")
        assert body["normalized_payload"]["type"] == "bim"
        assert body["normalized_payload"]["normalized"] is True

    @pytest.mark.asyncio
    async def test_ingest_sensor_data(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.post(
            "/ingest",
            headers=_auth_headers(),
            json={
                "source_type": "sensor",
                "raw_payload": {
                    "readings": [{"temp": 22.5, "ts": "2026-01-01T00:00:00Z"}],
                    "device_id": "sensor-42",
                },
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["normalized_payload"]["type"] == "sensor"
        assert body["normalized_payload"]["device_id"] == "sensor-42"

    @pytest.mark.asyncio
    async def test_ingest_unknown_source_type(self, ingestion_gateway_client):
        """Unknown source types should still be accepted with normalized=False."""
        response = await ingestion_gateway_client.post(
            "/ingest",
            headers=_auth_headers(),
            json={
                "source_type": "lidar",
                "raw_payload": {"points": [1, 2, 3]},
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["normalized_payload"]["normalized"] is False

    @pytest.mark.asyncio
    async def test_ingest_missing_fields_returns_422(self, ingestion_gateway_client):
        """Omitting required fields should trigger validation error."""
        response = await ingestion_gateway_client.post(
            "/ingest",
            headers=_auth_headers(),
            json={"source_type": "bim"},
        )

        assert response.status_code == 422


class TestListRecordsEndpoint:
    """Tests for GET /ingest."""

    @pytest.mark.asyncio
    async def test_list_records_empty(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.get("/ingest", headers=_auth_headers())

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)

    @pytest.mark.asyncio
    async def test_list_records_after_ingest(self, ingestion_gateway_client):
        # Ingest a record first
        await ingestion_gateway_client.post(
            "/ingest",
            headers=_auth_headers(),
            json={
                "source_type": "document",
                "raw_payload": {"content": "specification text", "doc_type": "spec"},
            },
        )

        response = await ingestion_gateway_client.get("/ingest", headers=_auth_headers())

        assert response.status_code == 200
        body = response.json()
        assert len(body) >= 1


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, ingestion_gateway_client):
        response = await ingestion_gateway_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "ingestion-gateway"
