"""
Strategy Agent v1 - Validator
================================
Post-generation quality checks.
"""
from typing import List

from app.agents.strategy.schemas.output import StrategyOutput


def validate_strategy_output(output: StrategyOutput) -> List[str]:
    """
    Run quality checks on strategy output.
    """
    violations = []

    # Check 1: Empty TOWS cells
    if not output.tows_matrix.SO:
        violations.append("SO strategies are empty")
    if not output.tows_matrix.WO:
        violations.append("WO strategies are empty")

    # Check 2: All strategies must have anchors
    for cell in ["SO", "ST", "WO", "WT"]:
        for s in getattr(output.tows_matrix, cell):
            if not s.anchors:
                violations.append(f"{s.strategy_id} has no anchors")

    # Check 3: Priority actions exist
    if not output.priority_action_plan:
        violations.append("No priority actions generated")

    return violations