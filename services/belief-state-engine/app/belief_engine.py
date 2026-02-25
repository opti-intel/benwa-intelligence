"""Core belief logic with Bayesian updates and graph-based propagation."""

from datetime import datetime
from typing import Optional

import numpy as np
from neo4j import Driver


# Default decay factor: how much confidence diminishes per hop in propagation
DEFAULT_DECAY_FACTOR = 0.8

# Default likelihood ratio for new evidence (positive evidence)
DEFAULT_LIKELIHOOD_RATIO = 1.5


class BeliefEngine:
    """Maintains and updates probabilistic belief states using Bayesian reasoning."""

    def __init__(self, neo4j_driver: Driver):
        self._driver = neo4j_driver
        self._history: dict[str, list[dict]] = {}  # keyed by "entity_type:entity_id"

    # ------------------------------------------------------------------
    # Bayesian update
    # ------------------------------------------------------------------
    def update_belief(
        self,
        entity_type: str,
        entity_id: str,
        new_evidence: dict,
        prior_confidence: float,
    ) -> float:
        """
        Calculate updated confidence using a simple Bayesian update.

        Uses the odds form of Bayes' theorem:
            posterior_odds = likelihood_ratio * prior_odds

        The likelihood ratio is derived from the evidence strength.
        Returns the updated confidence clamped to [0, 1].
        """
        key = f"{entity_type}:{entity_id}"

        # Determine likelihood ratio from evidence
        evidence_strength = new_evidence.get("strength", 0.5)
        # Map strength [0,1] to a likelihood ratio centred around 1.0
        # strength > 0.5 -> supports hypothesis, strength < 0.5 -> weakens it
        likelihood_ratio = 1.0 + (evidence_strength - 0.5) * 2.0 * (DEFAULT_LIKELIHOOD_RATIO - 1.0)
        likelihood_ratio = max(likelihood_ratio, 0.01)  # avoid zero/negative

        # Convert prior to odds, apply likelihood ratio, convert back
        prior_odds = prior_confidence / (1.0 - prior_confidence + 1e-10)
        posterior_odds = likelihood_ratio * prior_odds
        posterior_confidence = posterior_odds / (1.0 + posterior_odds)

        # Clamp
        posterior_confidence = float(np.clip(posterior_confidence, 0.0, 1.0))

        # Record history
        self._record_history(key, prior_confidence, posterior_confidence, new_evidence)

        return posterior_confidence

    # ------------------------------------------------------------------
    # Belief propagation
    # ------------------------------------------------------------------
    def propagate_beliefs(
        self,
        entity_type: str,
        entity_id: str,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
    ) -> list[dict]:
        """
        Propagate belief changes to graph neighbors with a decay factor.

        Retrieves neighbors from Neo4j and computes propagated confidence
        for each. Returns a list of dicts describing the updates.
        """
        key = f"{entity_type}:{entity_id}"
        history = self._history.get(key, [])

        # Use the most recent update to determine the belief delta
        if not history:
            return []

        latest = history[-1]
        source_confidence = latest["posterior"]

        # Fetch neighbors from Neo4j
        neighbors = self._get_neighbors_from_graph(entity_type, entity_id)

        updates: list[dict] = []
        for neighbor in neighbors:
            propagated_confidence = float(
                np.clip(source_confidence * decay_factor, 0.0, 1.0)
            )
            updates.append({
                "entity_type": neighbor["label"],
                "entity_id": neighbor["entity_id"],
                "propagated_confidence": round(propagated_confidence, 6),
                "decay_factor": decay_factor,
                "source": key,
            })

        return updates

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def get_belief_history(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[dict]:
        """Return the full history of belief updates for an entity."""
        key = f"{entity_type}:{entity_id}"
        return list(self._history.get(key, []))

    # ------------------------------------------------------------------
    # Risk score
    # ------------------------------------------------------------------
    def calculate_risk_score(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict:
        """
        Compute a risk score from the belief state.

        Risk is inversely related to confidence: low confidence in positive
        outcomes translates to high risk. Also factors in belief volatility
        (variance of recent confidence values).
        """
        key = f"{entity_type}:{entity_id}"
        history = self._history.get(key, [])

        if not history:
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "risk_score": 0.5,
                "volatility": 0.0,
                "data_points": 0,
            }

        confidences = [h["posterior"] for h in history]
        current_confidence = confidences[-1]
        volatility = float(np.std(confidences)) if len(confidences) > 1 else 0.0

        # Risk formula: base risk from low confidence + volatility penalty
        base_risk = 1.0 - current_confidence
        volatility_penalty = volatility * 0.5
        risk_score = float(np.clip(base_risk + volatility_penalty, 0.0, 1.0))

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "risk_score": round(risk_score, 6),
            "current_confidence": round(current_confidence, 6),
            "volatility": round(volatility, 6),
            "data_points": len(confidences),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _record_history(
        self,
        key: str,
        prior: float,
        posterior: float,
        evidence: dict,
    ) -> None:
        if key not in self._history:
            self._history[key] = []
        self._history[key].append({
            "prior": round(prior, 6),
            "posterior": round(posterior, 6),
            "evidence": evidence,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def _get_neighbors_from_graph(
        self,
        label: str,
        entity_id: str,
    ) -> list[dict]:
        """Query Neo4j for immediate neighbors of a node."""
        query = (
            f"MATCH (n:{label} {{entity_id: $entity_id}})-[r]-(m) "
            f"RETURN labels(m) AS labels, m.entity_id AS entity_id, type(r) AS rel_type"
        )
        results = []
        with self._driver.session() as session:
            records = session.run(query, entity_id=entity_id)
            for record in records:
                labels = record["labels"]
                results.append({
                    "label": labels[0] if labels else "Unknown",
                    "entity_id": record["entity_id"],
                    "rel_type": record["rel_type"],
                })
        return results
