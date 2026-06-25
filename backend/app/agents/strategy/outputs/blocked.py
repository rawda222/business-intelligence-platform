"""
Strategy Agent v1 - BLOCKED Output
===================================
Used when SWOT validation fails.
"""
from typing import Any

from app.agents.strategy.schemas.output import StrategyOutput
from app.agents.strategy.schemas.quality import StrategyQualityReport
from app.agents.strategy.schemas.tows import TOWSMatrix
from app.agents.strategy.enums import StrategicPosture


def build_blocked_output(swot_output: Any) -> StrategyOutput:
    """
    Build a BLOCKED StrategyOutput when SWOT validation has failed.
    """
    if hasattr(swot_output, "model_dump"):
        sd = swot_output.model_dump()
    else:
        sd = swot_output or {}

    validation = sd.get("validation_results", {}) or {}
    status = validation.get("overall_status", "UNKNOWN")
    violations = validation.get("violations", []) or []

    return StrategyOutput(
        business_type=sd.get("business_type", "unknown"),
        strategic_posture=StrategicPosture.BLOCKED,
        posture_rationale=(
            f"SWOT validation status is {status}. "
            f"Violations: {violations}. "
            "Strategy generation blocked until SWOT output passes validation."
        ),
        tows_matrix=TOWSMatrix(),
        priority_action_plan=[],
        resource_assessment=[],
        campaign_brief_feed=[],
        strategy_quality_report=StrategyQualityReport(
            overall_status="FAIL",
            warnings=["SWOT validation FAIL — strategy generation blocked."]
        ),
        meta={
            "blocked_reason": "swot_validation_fail",
            "validation_status": status,
        }
    )