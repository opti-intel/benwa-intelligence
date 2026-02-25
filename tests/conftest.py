"""Shared fixtures for benwa-intelligence test suite."""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Path setup: ensure services/ and services/shared/ are importable
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")

for p in [SERVICES_DIR, os.path.join(SERVICES_DIR, "shared")]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Patch heavy external dependencies before importing service apps
# ---------------------------------------------------------------------------

# Kafka — prevent real connections during import / lifespan
_kafka_producer_mock = AsyncMock()
_kafka_producer_mock.start = AsyncMock()
_kafka_producer_mock.stop = AsyncMock()
_kafka_producer_mock.send_and_wait = AsyncMock()

patch("shared.kafka_utils.get_kafka_producer", new=AsyncMock(return_value=_kafka_producer_mock)).start()
patch("shared.kafka_utils.publish_event", new=AsyncMock()).start()

# Neo4j — mock the driver so belief-state-engine doesn't need a real DB
_mock_neo4j_driver = MagicMock()
_mock_session = MagicMock()
_mock_session.run.return_value = []
_mock_neo4j_driver.session.return_value.__enter__ = MagicMock(return_value=_mock_session)
_mock_neo4j_driver.session.return_value.__exit__ = MagicMock(return_value=False)
_mock_neo4j_driver.close = MagicMock()

patch("shared.db.get_db", new=AsyncMock()).start()

# Solver-engine consumer — prevent Kafka background task
patch("app.consumer.start_consumer", new=AsyncMock()).start()
patch("app.consumer.stop_consumer", new=AsyncMock()).start()

# ---------------------------------------------------------------------------
# Import apps AFTER patching
# ---------------------------------------------------------------------------
# Each service has its app object at  services/<name>/app/main.py -> app
# We add each service dir to sys.path so `from app.main import app` works.

# -- Semantic Airlock --
sys.path.insert(0, os.path.join(SERVICES_DIR, "semantic-airlock"))
from app.main import app as semantic_airlock_app  # noqa: E402

# -- Ingestion Gateway --
# Remove semantic-airlock app path and add ingestion-gateway
sys.path.insert(0, os.path.join(SERVICES_DIR, "ingestion-gateway"))
from app.main import app as _ingestion_app_candidate  # noqa: E402

# Because both services use `app.main`, we need to reload for each service.
# Instead we import them via importlib to isolate modules.
import importlib

def _import_service_app(service_name: str):
    """Import a service's FastAPI app in an isolated manner."""
    svc_dir = os.path.join(SERVICES_DIR, service_name)
    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

    # Construct the full module path
    spec = importlib.util.spec_from_file_location(
        f"{service_name}.app.main",
        os.path.join(svc_dir, "app", "main.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app


# Re-import cleanly via importlib to avoid module-name collisions
semantic_airlock_app = _import_service_app("semantic-airlock")
ingestion_gateway_app = _import_service_app("ingestion-gateway")

# For belief-state-engine and solver-engine we need extra patches at import time
with patch("app.consumer.consume_raw_ingestion", new=AsyncMock()):
    pass  # semantic-airlock consumer already handled

# Belief-state-engine needs Neo4j patches
_bse_dir = os.path.join(SERVICES_DIR, "belief-state-engine")
sys.path.insert(0, _bse_dir)

with patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687"}):
    with patch("app.graph.get_neo4j_driver", return_value=_mock_neo4j_driver):
        with patch("app.graph.GraphDatabase", MagicMock()):
            belief_state_app = _import_service_app("belief-state-engine")

# Solver-engine
_solver_dir = os.path.join(SERVICES_DIR, "solver-engine")
sys.path.insert(0, _solver_dir)

with patch("app.consumer.start_consumer", new=AsyncMock()):
    with patch("app.consumer.stop_consumer", new=AsyncMock()):
        solver_engine_app = _import_service_app("solver-engine")


# ---------------------------------------------------------------------------
# Async HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def semantic_airlock_client():
    """Async HTTP client for the Semantic Airlock service."""
    transport = ASGITransport(app=semantic_airlock_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def belief_state_client():
    """Async HTTP client for the Belief State Engine service."""
    transport = ASGITransport(app=belief_state_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def solver_engine_client():
    """Async HTTP client for the Solver Engine service."""
    transport = ASGITransport(app=solver_engine_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def ingestion_gateway_client():
    """Async HTTP client for the Ingestion Gateway service."""
    transport = ASGITransport(app=ingestion_gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_valid_plan():
    """A plan that passes all validators (safety + compliance + semantic)."""
    return {
        "safety_plan": "Full PPE required on site",
        "emergency_procedures": "Evacuate via stairwell B",
        "ppe_requirements": "Hard hats, steel-toed boots",
        "building_codes": ["IBC-2021"],
        "permits": ["BP-2024-001"],
        "environmental_impact": "Low impact — no wetlands affected",
        "description": "Phase 1 foundation pour for Building A",
    }


@pytest.fixture
def sample_invalid_plan():
    """A plan missing safety fields — should fail safety validation."""
    return {
        "building_codes": ["IBC-2021"],
        "permits": ["BP-2024-001"],
        "environmental_impact": "Low impact",
        "description": "Phase 1 foundation pour",
    }


@pytest.fixture
def sample_project_id():
    return str(uuid4())


@pytest.fixture
def sample_tasks():
    """Simple list of 3 tasks with dependencies for scheduling tests."""
    return [
        {"id": "excavation", "duration": 5.0, "dependencies": []},
        {"id": "foundation", "duration": 3.0, "dependencies": ["excavation"]},
        {"id": "framing", "duration": 7.0, "dependencies": ["foundation"]},
    ]


@pytest.fixture
def sample_resources():
    """Resources for allocation tests."""
    return [
        {"id": "crane-1", "capacity": 100},
        {"id": "crane-2", "capacity": 80},
        {"id": "loader-1", "capacity": 50},
    ]


@pytest.fixture
def sample_demands():
    """Demands for allocation tests."""
    return [
        {"id": "lift-steel", "required_capacity": 90, "priority": 10},
        {"id": "lift-concrete", "required_capacity": 60, "priority": 8},
        {"id": "move-earth", "required_capacity": 40, "priority": 5},
    ]


@pytest.fixture
def mock_neo4j_driver():
    """Pre-configured mock Neo4j driver."""
    return _mock_neo4j_driver
