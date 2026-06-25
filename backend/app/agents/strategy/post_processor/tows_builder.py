"""
Strategy Agent v1 - TOWS Builder
=================================
Convert LLM output into structured TOWSMatrix.
"""
from typing import Dict, List

from app.agents.strategy.schemas.tows import TOWSMatrix, TOWSStrategy
from app.agents.strategy.schemas.anchors import StrategyAnchor
from app.agents.strategy.enums import StrategyType


def build_tows_matrix(llm_output: Dict, valid_item_ids: set) -> TOWSMatrix:
    """
    Convert raw LLM output into TOWSMatrix with validation.

    Args:
        llm_output: Parsed JSON from LLM
        valid_item_ids: Set of valid SWOT item_ids

    Returns:
        TOWSMatrix object
    """
    tows = llm_output.get("tows_matrix", {}) or {}

    return TOWSMatrix(
        SO=_build_strategies(tows.get("SO", []), StrategyType.SO, valid_item_ids),
        ST=_build_strategies(tows.get("ST", []), StrategyType.ST, valid_item_ids),
        WO=_build_strategies(tows.get("WO", []), StrategyType.WO, valid_item_ids),
        WT=_build_strategies(tows.get("WT", []), StrategyType.WT, valid_item_ids),
    )


def _build_strategies(
    strategies: List[Dict],
    strategy_type: str,
    valid_item_ids: set,
) -> List[TOWSStrategy]:
    """
    Convert raw strategy list into structured TOWSStrategy objects.
    """
    output = []

    for i, s in enumerate(strategies):
        # Validate anchor IDs
        anchor_ids = s.get("anchor_item_ids", [])
        valid_anchors = [
            aid for aid in anchor_ids if aid in valid_item_ids
        ]

        # Build anchor objects
        anchors = [
            StrategyAnchor(
                item_id=aid,
                title=f"Anchor {aid}",
                quadrant="unknown",
                confidence="unknown",
                strategic_priority=0.0,
            )
            for aid in valid_anchors
        ]

        strategy = TOWSStrategy(
            strategy_id=f"{strategy_type}_{i+1}",
            strategy_type=strategy_type,
            title=s.get("title", "Untitled Strategy"),
            description=s.get("description", ""),
            rationale=s.get("rationale", ""),
            anchors=anchors,
            confidence=s.get("confidence", "exploratory"),
            horizon=s.get("horizon", "short_term"),
            estimated_effort=s.get("estimated_effort", "medium"),
            estimated_impact=s.get("estimated_impact", "medium"),
            priority_rank=i + 1,
            tags=s.get("tags", []),
            requires_manual_review=False,
            downstream_campaign_eligible=True,
            watchout_flag=None,
        )

        output.append(strategy)

    return output