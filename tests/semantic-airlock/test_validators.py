"""Tests for semantic-airlock validators."""

import sys
import os

import pytest

# Ensure services are importable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "semantic-airlock"))
sys.path.insert(0, SERVICES_DIR)

from app.validators import (
    SafetyValidator,
    ComplianceValidator,
    SemanticValidator,
    run_all_validators,
    REQUIRED_SAFETY_FIELDS,
    REQUIRED_COMPLIANCE_FIELDS,
)


# ---------------------------------------------------------------------------
# SafetyValidator
# ---------------------------------------------------------------------------

class TestSafetyValidator:
    """Tests for SafetyValidator."""

    @pytest.mark.asyncio
    async def test_passing_plan(self, sample_valid_plan):
        validator = SafetyValidator()
        result = await validator.validate(sample_valid_plan)

        assert result["validator"] == "safety"
        assert result["passed"] is True
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_failing_plan_missing_all_safety_fields(self):
        validator = SafetyValidator()
        result = await validator.validate({"description": "bare plan"})

        assert result["passed"] is False
        assert len(result["issues"]) == len(REQUIRED_SAFETY_FIELDS)
        for field in REQUIRED_SAFETY_FIELDS:
            assert any(field in issue for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_failing_plan_empty_safety_field(self):
        """A field that is present but falsy should still fail."""
        validator = SafetyValidator()
        plan = {
            "safety_plan": "",
            "emergency_procedures": "Evacuate",
            "ppe_requirements": "Hard hats",
        }
        result = await validator.validate(plan)

        assert result["passed"] is False
        assert any("safety_plan" in i for i in result["issues"])

    @pytest.mark.asyncio
    async def test_partial_safety_fields(self):
        """Only one safety field present -> two issues."""
        validator = SafetyValidator()
        plan = {"safety_plan": "Present"}
        result = await validator.validate(plan)

        assert result["passed"] is False
        assert len(result["issues"]) == 2


# ---------------------------------------------------------------------------
# ComplianceValidator
# ---------------------------------------------------------------------------

class TestComplianceValidator:
    """Tests for ComplianceValidator."""

    @pytest.mark.asyncio
    async def test_passing_plan(self, sample_valid_plan):
        validator = ComplianceValidator()
        result = await validator.validate(sample_valid_plan)

        assert result["validator"] == "compliance"
        assert result["passed"] is True
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_failing_plan_missing_all_compliance_fields(self):
        validator = ComplianceValidator()
        result = await validator.validate({"description": "no compliance"})

        assert result["passed"] is False
        assert len(result["issues"]) == len(REQUIRED_COMPLIANCE_FIELDS)

    @pytest.mark.asyncio
    async def test_failing_plan_empty_compliance_field(self):
        validator = ComplianceValidator()
        plan = {
            "building_codes": [],
            "permits": ["P-001"],
            "environmental_impact": "Low",
        }
        result = await validator.validate(plan)

        assert result["passed"] is False
        assert any("building_codes" in i for i in result["issues"])


# ---------------------------------------------------------------------------
# SemanticValidator
# ---------------------------------------------------------------------------

class TestSemanticValidator:
    """Tests for SemanticValidator structural checks (no API key set)."""

    @pytest.mark.asyncio
    async def test_empty_plan_fails(self):
        validator = SemanticValidator()
        result = await validator.validate({})

        assert result["validator"] == "semantic"
        assert result["passed"] is False
        assert any("empty" in i.lower() for i in result["issues"])

    @pytest.mark.asyncio
    async def test_plan_without_description_fails(self):
        """Plan with content but no descriptive field should fail (fallback mode)."""
        validator = SemanticValidator()
        # Ensure no ANTHROPIC_API_KEY is set for fallback path
        orig = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = await validator.validate({"safety_plan": "yes"})
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig

        assert result["passed"] is False
        assert any("descriptive field" in i.lower() for i in result["issues"])

    @pytest.mark.asyncio
    async def test_plan_with_description_passes(self):
        """Plan with a descriptive field should pass structural checks."""
        validator = SemanticValidator()
        orig = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = await validator.validate({"description": "Build a wall"})
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig

        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_plan_with_summary_passes(self):
        """'summary' is also an acceptable descriptive field."""
        validator = SemanticValidator()
        orig = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = await validator.validate({"summary": "Project overview"})
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig

        assert result["passed"] is True


# ---------------------------------------------------------------------------
# run_all_validators
# ---------------------------------------------------------------------------

class TestRunAllValidators:
    """Tests for the run_all_validators aggregation function."""

    @pytest.mark.asyncio
    async def test_returns_three_results(self, sample_valid_plan):
        results = await run_all_validators(sample_valid_plan)

        assert len(results) == 3
        validator_names = {r["validator"] for r in results}
        assert validator_names == {"safety", "compliance", "semantic"}

    @pytest.mark.asyncio
    async def test_all_pass_for_valid_plan(self, sample_valid_plan):
        results = await run_all_validators(sample_valid_plan)

        for r in results:
            assert r["passed"] is True, f"{r['validator']} should pass"

    @pytest.mark.asyncio
    async def test_mixed_results_for_invalid_plan(self, sample_invalid_plan):
        """Invalid plan should fail safety but pass compliance."""
        orig = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            results = await run_all_validators(sample_invalid_plan)
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig

        by_name = {r["validator"]: r for r in results}
        assert by_name["safety"]["passed"] is False
        assert by_name["compliance"]["passed"] is True
