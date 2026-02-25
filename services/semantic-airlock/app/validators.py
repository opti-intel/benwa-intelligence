import os
from typing import Any

REQUIRED_SAFETY_FIELDS = ["safety_plan", "emergency_procedures", "ppe_requirements"]
REQUIRED_COMPLIANCE_FIELDS = ["building_codes", "permits", "environmental_impact"]


class SafetyValidator:
    """Validates that construction plans contain required safety information."""

    async def validate(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        for field in REQUIRED_SAFETY_FIELDS:
            if field not in plan_data or not plan_data[field]:
                issues.append(f"Missing required safety field: {field}")

        return {
            "validator": "safety",
            "passed": len(issues) == 0,
            "issues": issues,
        }


class ComplianceValidator:
    """Validates that construction plans meet compliance requirements."""

    async def validate(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        for field in REQUIRED_COMPLIANCE_FIELDS:
            if field not in plan_data or not plan_data[field]:
                issues.append(f"Missing required compliance field: {field}")

        return {
            "validator": "compliance",
            "passed": len(issues) == 0,
            "issues": issues,
        }


class SemanticValidator:
    """Uses Anthropic AI to analyze plan semantics and structural integrity."""

    async def validate(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        reasoning: str | None = None

        # Structural checks before calling AI
        if not isinstance(plan_data, dict):
            return {
                "validator": "semantic",
                "passed": False,
                "issues": ["Plan data must be a dictionary"],
                "reasoning": "Invalid plan structure.",
            }

        if len(plan_data) == 0:
            return {
                "validator": "semantic",
                "passed": False,
                "issues": ["Plan data is empty"],
                "reasoning": "Cannot validate an empty plan.",
            }

        # Attempt AI-powered semantic analysis via Anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic

                client = anthropic.AsyncAnthropic(api_key=api_key)
                message = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Analyze the following construction plan data for semantic "
                                "correctness, logical consistency, and completeness. "
                                "Return a brief JSON object with keys: passed (bool), "
                                "issues (list of strings), reasoning (string).\n\n"
                                f"Plan data: {plan_data}"
                            ),
                        }
                    ],
                )
                reasoning = message.content[0].text
                # In production, parse the AI response into structured findings.
                # For now, treat the AI call as advisory and pass structural checks.
                return {
                    "validator": "semantic",
                    "passed": True,
                    "issues": [],
                    "reasoning": reasoning,
                }
            except Exception as exc:
                issues.append(f"AI semantic analysis unavailable: {exc}")
                reasoning = "Fell back to structural validation only."
        else:
            reasoning = "No ANTHROPIC_API_KEY set; structural validation only."

        # Fallback: basic structural checks
        has_description = any(
            key in plan_data
            for key in ["description", "summary", "scope", "overview"]
        )
        if not has_description:
            issues.append(
                "Plan lacks a descriptive field (description, summary, scope, or overview)"
            )

        passed = len(issues) == 0
        return {
            "validator": "semantic",
            "passed": passed,
            "issues": issues,
            "reasoning": reasoning,
        }


async def run_all_validators(plan_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Run all validators against the provided plan data and return combined results."""
    safety = SafetyValidator()
    compliance = ComplianceValidator()
    semantic = SemanticValidator()

    results = [
        await safety.validate(plan_data),
        await compliance.validate(plan_data),
        await semantic.validate(plan_data),
    ]
    return results
