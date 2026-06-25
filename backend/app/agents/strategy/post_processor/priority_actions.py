"""
Strategy Agent v1 - Priority Actions Builder
==============================================
Convert TOWS strategies into ranked priority actions.
"""
from typing import List

from app.agents.strategy.schemas.tows import TOWSMatrix
from app.agents.strategy.schemas.actions import PriorityAction
from app.agents.strategy.config import (
    MAX_PRIORITY_ACTIONS,
    CONFIDENCE_WEIGHTS,
    IMPACT_WEIGHTS,
    EFFORT_WEIGHTS,
)


def build_priority_actions(tows: TOWSMatrix) -> List[PriorityAction]:
    """
    Convert all TOWS strategies into ranked priority actions.
    """
    strategies = (
        tows.SO +
        tows.ST +
        tows.WO +
        tows.WT
    )

    actions = []

    for i, s in enumerate(strategies):
        score = _compute_priority_score(s)

        action = PriorityAction(
            action_id=f"A_{i+1}",
            title=s.title,
            description=s.description,
            linked_strategy_ids=[s.strategy_id],
            horizon=s.horizon,
            owner_area=_infer_owner_area(s),
            priority_rank=0,  # will assign after sort
            confidence=s.confidence,
            effort=s.estimated_effort,
            impact=s.estimated_impact,
            success_metric="TBD",
            requires_manual_review=s.requires_manual_review,
            blocked_by=[],
        )

        actions.append((score, action))

    # Sort descending
    actions.sort(key=lambda x: x[0], reverse=True)

    # Assign ranks
    final = []
    for rank, (_, act) in enumerate(actions[:MAX_PRIORITY_ACTIONS], start=1):
        act.priority_rank = rank
        final.append(act)

    return final


def _compute_priority_score(strategy) -> float:
    """
    Compute strategy priority score using:
    score = impact × confidence / effort
    """
    conf = CONFIDENCE_WEIGHTS.get(strategy.confidence, 0.5)
    impact = IMPACT_WEIGHTS.get(strategy.estimated_impact, 2)
    effort = EFFORT_WEIGHTS.get(strategy.estimated_effort, 2)

    return (impact * conf) / max(1, effort)


def _infer_owner_area(strategy) -> str:
    """
    Infer owner area from strategy type.
    """
    if strategy.strategy_type == "SO":
        return "growth"

    if strategy.strategy_type == "WO":
        return "operations"

    if strategy.strategy_type == "ST":
        return "risk"

    if strategy.strategy_type == "WT":
        return "defense"

    return "general"
