"""
Strategy Agent v1 - Dry Run Output
===================================
Placeholder output when dry_run=True.
"""
from typing import Any

from app.agents.strategy.schemas.output import StrategyOutput
from app.agents.strategy.schemas.quality import StrategyQualityReport
from app.agents.strategy.schemas.tows import TOWSMatrix
from app.agents.strategy.enums import StrategicPosture
from app.agents.strategy.config import ENGINE_VERSION


def build_dry_run_output(swot_output: Any, elapsed_ms: int) -> StrategyOutput:
    """
    Placeholder StrategyOutput for pipeline testing (no LLM call).
    """
    if hasattr(swot_output, "model_dump"):
        sd = swot_output.model_dump()
    else:
        sd = swot_output or {}

    return StrategyOutput(
        business_type=sd.get("business_type", "unknown"),
        engine_version=ENGINE_VERSION,
        strategic_posture=StrategicPosture.LEVERAGE_LED,
        posture_rationale="[DRY RUN — LLM not called]",
        tows_matrix=TOWSMatrix(),
        priority_action_plan=[],
        resource_assessment=[],
        campaign_brief_feed=[],
        strategy_quality_report=StrategyQualityReport(
            overall_status="PASS",
            warnings=["dry_run mode — no LLM output generated"]
        ),
        meta={
            "engine_version": ENGINE_VERSION,
            "dry_run": True,
            "processing_time_ms": elapsed_ms,
        }
    )