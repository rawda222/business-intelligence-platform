"""
Strategy Agent v1 - Strategic Posture Classification
=====================================================
Determine the overall strategic posture based on SWOT signals.
"""
from typing import Dict

from app.agents.strategy.enums import StrategicPosture
from app.agents.strategy.config import LEVERAGE_PRIORITY_FLOOR


def classify_strategic_posture(filtered: Dict) -> str:
    """
    Classify strategic posture based on SWOT patterns.

    Logic:
    - Many strong strengths → LEVERAGE_LED
    - Many strong weaknesses → IMPROVEMENT_LED
    - Many threats → DEFENSE_LED
    - Weak everything → CONTINGENCY_LED
    - Mixed → BALANCED
    """

    strengths = filtered.get("strengths", [])
    weaknesses = filtered.get("weaknesses", [])
    opportunities = filtered.get("opportunities", [])
    threats = filtered.get("threats", [])

    count_s = len(strengths)
    count_w = len(weaknesses)
    count_o = len(opportunities)
    count_t = len(threats)

    # Simple strategic heuristics
    if count_s >= 2 and count_o >= 1:
        return StrategicPosture.LEVERAGE_LED

    if count_w >= 2 and count_o >= 1:
        return StrategicPosture.IMPROVEMENT_LED

    if count_t >= 2:
        return StrategicPosture.DEFENSE_LED

    if count_s == 0 and count_w >= 2:
        return StrategicPosture.CONTINGENCY_LED

    return StrategicPosture.BALANCED
