"""Tests for the BeliefEngine core logic."""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "belief-state-engine"))
sys.path.insert(0, SERVICES_DIR)

from app.belief_engine import BeliefEngine, DEFAULT_DECAY_FACTOR


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()
    mock_session = MagicMock()
    mock_session.run.return_value = iter([])
    driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


@pytest.fixture
def engine(mock_driver):
    """Create a BeliefEngine with a mocked Neo4j driver."""
    return BeliefEngine(mock_driver)


# ---------------------------------------------------------------------------
# update_belief
# ---------------------------------------------------------------------------

class TestUpdateBelief:
    """Tests for Bayesian belief update."""

    def test_positive_evidence_increases_confidence(self, engine):
        """Evidence with strength > 0.5 should increase confidence."""
        prior = 0.5
        posterior = engine.update_belief(
            entity_type="task",
            entity_id="t1",
            new_evidence={"strength": 0.9},
            prior_confidence=prior,
        )

        assert posterior > prior

    def test_negative_evidence_decreases_confidence(self, engine):
        """Evidence with strength < 0.5 should decrease confidence."""
        prior = 0.5
        posterior = engine.update_belief(
            entity_type="task",
            entity_id="t2",
            new_evidence={"strength": 0.1},
            prior_confidence=prior,
        )

        assert posterior < prior

    def test_neutral_evidence_keeps_confidence_similar(self, engine):
        """Evidence with strength == 0.5 should leave confidence roughly unchanged."""
        prior = 0.6
        posterior = engine.update_belief(
            entity_type="task",
            entity_id="t3",
            new_evidence={"strength": 0.5},
            prior_confidence=prior,
        )

        assert abs(posterior - prior) < 0.01

    def test_confidence_clamped_to_unit_interval(self, engine):
        """Even with extreme evidence, confidence stays in [0, 1]."""
        posterior_high = engine.update_belief(
            entity_type="task",
            entity_id="t4",
            new_evidence={"strength": 1.0},
            prior_confidence=0.99,
        )
        assert 0.0 <= posterior_high <= 1.0

        posterior_low = engine.update_belief(
            entity_type="task",
            entity_id="t5",
            new_evidence={"strength": 0.0},
            prior_confidence=0.01,
        )
        assert 0.0 <= posterior_low <= 1.0

    def test_records_history(self, engine):
        """Each update should be recorded in the engine's history."""
        engine.update_belief("task", "t6", {"strength": 0.8}, 0.5)
        engine.update_belief("task", "t6", {"strength": 0.9}, 0.6)

        history = engine.get_belief_history("task", "t6")
        assert len(history) == 2
        assert history[0]["prior"] == 0.5
        assert "posterior" in history[0]
        assert "timestamp" in history[0]

    def test_default_evidence_strength(self, engine):
        """When no strength key is provided, default of 0.5 should be used."""
        prior = 0.5
        posterior = engine.update_belief(
            entity_type="task",
            entity_id="t7",
            new_evidence={},
            prior_confidence=prior,
        )
        # With default strength 0.5, confidence should remain close to prior
        assert abs(posterior - prior) < 0.01


# ---------------------------------------------------------------------------
# calculate_risk_score
# ---------------------------------------------------------------------------

class TestCalculateRiskScore:
    """Tests for risk score calculation."""

    def test_no_history_returns_default(self, engine):
        """Without any updates, risk should be the default 0.5."""
        result = engine.calculate_risk_score("task", "unknown")

        assert result["risk_score"] == 0.5
        assert result["volatility"] == 0.0
        assert result["data_points"] == 0

    def test_low_confidence_yields_high_risk(self, engine):
        """Low posterior confidence should produce a higher risk score."""
        engine.update_belief("task", "risky", {"strength": 0.1}, 0.3)

        result = engine.calculate_risk_score("task", "risky")
        assert result["risk_score"] > 0.5

    def test_high_confidence_yields_low_risk(self, engine):
        """High posterior confidence should produce a lower risk score."""
        engine.update_belief("task", "safe", {"strength": 0.95}, 0.8)

        result = engine.calculate_risk_score("task", "safe")
        assert result["risk_score"] < 0.5

    def test_volatility_increases_risk(self, engine):
        """Multiple updates with varying confidence should increase volatility penalty."""
        engine.update_belief("task", "volatile", {"strength": 0.9}, 0.3)
        engine.update_belief("task", "volatile", {"strength": 0.1}, 0.8)
        engine.update_belief("task", "volatile", {"strength": 0.9}, 0.3)

        result = engine.calculate_risk_score("task", "volatile")
        assert result["volatility"] > 0.0
        assert result["data_points"] == 3


# ---------------------------------------------------------------------------
# propagate_beliefs (with mocked Neo4j)
# ---------------------------------------------------------------------------

class TestPropagateBeliefs:
    """Tests for belief propagation through the graph."""

    def test_no_history_returns_empty(self, engine):
        """Propagation with no prior updates should return nothing."""
        updates = engine.propagate_beliefs("task", "no-history")
        assert updates == []

    def test_propagation_applies_decay(self, engine, mock_driver):
        """Propagated confidence should be source * decay_factor."""
        # First create a history entry
        engine.update_belief("task", "src", {"strength": 0.9}, 0.5)

        # Mock the Neo4j neighbor query
        mock_session = MagicMock()
        mock_record = {
            "labels": ["Resource"],
            "entity_id": "r1",
            "rel_type": "USES",
        }
        mock_session.run.return_value = [mock_record]
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)

        updates = engine.propagate_beliefs("task", "src")
        assert len(updates) == 1
        assert updates[0]["entity_type"] == "Resource"
        assert updates[0]["entity_id"] == "r1"

        # Propagated confidence = source_posterior * DEFAULT_DECAY_FACTOR
        history = engine.get_belief_history("task", "src")
        source_posterior = history[-1]["posterior"]
        expected = round(source_posterior * DEFAULT_DECAY_FACTOR, 6)
        assert updates[0]["propagated_confidence"] == expected

    def test_no_neighbors_returns_empty(self, engine, mock_driver):
        """If Neo4j returns no neighbors, propagation returns empty list."""
        engine.update_belief("task", "isolated", {"strength": 0.8}, 0.5)

        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)

        updates = engine.propagate_beliefs("task", "isolated")
        assert updates == []
