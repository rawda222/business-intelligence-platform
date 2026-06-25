"""
Strategy Agent v1 - Main Pipeline
==================================
Orchestrates the full strategy generation process.
"""
import time
import logging
from typing import Any

from app.agents.strategy.schemas.output import StrategyOutput

# Reuse SWOT LLM chain
from app.agents.swot.llm.chain import call_llm_chain
from app.agents.swot.utils.json_parser import safe_parse_json

from app.agents.strategy.filtering import filter_strategy_inputs
from app.agents.strategy.prompts import (
    STRATEGY_SYSTEM_PROMPT,
    build_strategy_user_prompt,
)
from app.agents.strategy.outputs import (
    build_blocked_output,
    build_dry_run_output,
)
from app.agents.strategy.post_processor import (
    classify_strategic_posture,
    build_tows_matrix,
    build_priority_actions,
    build_resource_assessment,
    build_campaign_feed,
    validate_strategy_output,
)
from app.agents.strategy.utils import collect_valid_item_ids
from app.agents.strategy.enums import StrategicPosture


logger = logging.getLogger("strategy_agent_v1")


class StrategyAgent:
    """
    Main Strategy Agent orchestrator.
    """

    def __init__(self, llm_chain=None, dry_run=False):
        self.llm_chain = llm_chain or []
        self.dry_run = dry_run

    def run(self, swot_output: Any) -> StrategyOutput:
        start = time.time()

        # =========================================================
        # Step 1: Filter Inputs
        # =========================================================
        filtered = filter_strategy_inputs(swot_output)

        if filtered.get("validation_status") != "PASS":
            return build_blocked_output(swot_output)

        # =========================================================
        # Step 2: Dry Run Shortcut
        # =========================================================
        if self.dry_run:
            elapsed = int((time.time() - start) * 1000)
            return build_dry_run_output(swot_output, elapsed)

        # =========================================================
        # Step 3: Build Prompts
        # =========================================================
        system_prompt = STRATEGY_SYSTEM_PROMPT
        user_prompt = build_strategy_user_prompt(filtered)

        # =========================================================
        # Step 4: Call LLM
        # =========================================================
        response_text, _ = call_llm_chain(
            chain=self.llm_chain,
            system=system_prompt,
            user=user_prompt,
        )

        parsed = safe_parse_json(response_text) if response_text else {}

        # =========================================================
        # Step 5: Post Processing
        # =========================================================
        valid_ids = collect_valid_item_ids(filtered)

        tows_matrix = build_tows_matrix(parsed, valid_ids)
        actions = build_priority_actions(tows_matrix)
        resources = build_resource_assessment(actions)
        campaigns = build_campaign_feed(tows_matrix)

        posture = classify_strategic_posture(filtered)

        # =========================================================
        # Step 6: Build Output
        # =========================================================
        output = StrategyOutput(
            business_type=filtered.get("business_type", "unknown"),
            strategic_posture=posture,
            posture_rationale=f"Auto-detected posture: {posture}",
            tows_matrix=tows_matrix,
            priority_action_plan=actions,
            resource_assessment=resources,
            campaign_brief_feed=campaigns,
            meta={
                "processing_time_ms": int((time.time() - start) * 1000),
                "llm_used": True,
            }
        )

        # =========================================================
        # Step 7: Validation
        # =========================================================
        violations = validate_strategy_output(output)

        if violations:
            output.strategy_quality_report.overall_status = "WARN"
            output.strategy_quality_report.warnings.extend(violations)

        return output
