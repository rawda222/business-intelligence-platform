"""
SWOT Agent v7 - Stage 10: Validation Tests (FIX 14)
====================================================
Run 8 standalone validation tests on a SWOTOutput dict.
"""
import logging


logger = logging.getLogger("swot_agent_v7")


def validate_swot_output(output):
    """
    Run 8 standalone validation tests on a SWOTOutput dict.

    Returns:
        List of violation strings (empty if all tests pass).
    """
    violations = []

    swot_report = output.get("swot_report", {})

    # Test 1: All required top-level keys exist
    required_keys = [
        "swot_report",
        "watchouts",
        "derived_opportunities",
        "directional_competitive_signals",
        "strategic_summary",
        "strategic_context",
        "quality_report",
        "validation_results",
        "meta",
    ]
    for key in required_keys:
        if key not in output:
            violations.append(f"Missing required key: {key}")

    # Test 2: SWOT report has all 4 quadrants
    quadrants = ["strengths", "weaknesses", "opportunities", "threats"]
    for q in quadrants:
        if q not in swot_report:
            violations.append(f"Missing quadrant: {q}")

    # Test 3: Each SWOT item has required fields
    for quadrant in quadrants:
        for item in swot_report.get(quadrant, []):
            for field in ["item_id", "title", "reasoning", "source_theme"]:
                if field not in item:
                    violations.append(
                        f"Item in {quadrant} missing field: {field}"
                    )

    # Test 4: Watchouts have parent_theme
    for w in output.get("watchouts", []):
        if "parent_theme" not in w:
            violations.append(f"Watchout missing parent_theme: {w.get('title')}")

    # Test 5: Derived opportunities have parent linkage
    for do in output.get("derived_opportunities", []):
        if not do.get("derived_from"):
            violations.append(
                f"Derived opportunity missing derived_from: {do.get('title')}"
            )

    # Test 6: Engine meta is populated
    meta = output.get("meta", {})
    if not meta.get("engine_version"):
        violations.append("meta.engine_version missing")

    # Test 7: No confirmed weaknesses are shadows
    for w in swot_report.get("weaknesses", []):
        if w.get("is_shadow"):
            violations.append(
                f"Confirmed weakness should not be shadow: {w.get('title')}"
            )

    # Test 8: Strategic summary has key fields
    summary = output.get("strategic_summary", {})
    for field in ["main_advantage", "most_critical_risk", "best_growth_opportunity"]:
        if field not in summary:
            violations.append(f"Strategic summary missing field: {field}")

    if violations:
        logger.warning(
            f"[Stage 10] Validation found {len(violations)} violations"
        )
    else:
        logger.info("[Stage 10] All validation tests passed")

    return violations