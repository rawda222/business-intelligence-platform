"""
Strategy Agent v1 - Resource Grid Builder
==========================================
Build effort × impact matrix for actions.
"""
from typing import List

from app.agents.strategy.schemas.actions import PriorityAction
from app.agents.strategy.schemas.resources import ResourceAssessmentEntry


def build_resource_assessment(actions: List[PriorityAction]) -> List[ResourceAssessmentEntry]:
    """
    Build resource assessment grid from priority actions.
    """
    output = []

    for a in actions:
        quadrant = _classify_quadrant(a.effort, a.impact)

        entry = ResourceAssessmentEntry(
            action_id=a.action_id,
            title=a.title,
            effort=a.effort,
            impact=a.impact,
            horizon=a.horizon,
            quadrant_label=quadrant,
        )

        output.append(entry)

    return output


def _classify_quadrant(effort: str, impact: str) -> str:
    """
    Classify into effort-impact quadrant.
    """
    if impact == "high" and effort == "low":
        return "quick_win"

    if impact == "high" and effort == "high":
        return "major_bet"

    if impact == "low" and effort == "low":
        return "fill_in"

    if impact == "low" and effort == "high":
        return "thankless"

    return "fill_in"
