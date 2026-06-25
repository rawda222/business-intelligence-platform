"""
SWOT Agent v7 - Post Processor
==============================
Optional advanced post-processing utilities used by the pipeline.

This module provides additional helpers for:
- Computing PI (Performance-Importance) zones
- Computing vulnerability scores
- Building matrix outputs
- Item-level enrichment beyond the basic scoring

NOTE: The main pipeline orchestration is in pipeline.py.
This module exists for advanced use cases where you need to
post-process SWOT items independently.
"""
import logging
from typing import List, Optional


logger = logging.getLogger("swot_agent_v7")


def compute_pi_zone(performance_score: float, importance: float) -> str:
    """
    Compute Performance-Importance (PI) Zone for an item.

    PI Matrix zones:
    - "keep_up_good_work" (high importance + high performance)
    - "concentrate_here"  (high importance + low performance) 
    - "low_priority"      (low importance + low performance)
    - "possible_overkill" (low importance + high performance)

    Args:
        performance_score: 0-10
        importance: 0-10

    Returns:
        Zone label as string
    """
    high_perf = performance_score >= 6.0
    high_imp = importance >= 6.0

    if high_imp and high_perf:
        return "keep_up_good_work"
    elif high_imp and not high_perf:
        return "concentrate_here"
    elif not high_imp and high_perf:
        return "possible_overkill"
    else:
        return "low_priority"


def compute_vulnerability_score(
    confidence: float,
    performance_score: float,
    importance: float,
) -> float:
    """
    Compute vulnerability score (0-10).

    Higher = more vulnerable.

    Formula:
        vulnerability = importance × (1 - performance/10) × (1 - confidence)
    
    Logic:
    - High importance + low performance + low confidence = very vulnerable
    - Low importance OR high performance OR high confidence = less vulnerable

    Args:
        confidence: 0-1
        performance_score: 0-10
        importance: 0-10

    Returns:
        Vulnerability score (0-10)
    """
    perf_gap = 1.0 - (performance_score / 10.0)
    conf_gap = 1.0 - confidence
    
    vulnerability = importance * perf_gap * conf_gap
    return round(max(0.0, min(10.0, vulnerability)), 2)


def build_importance_performance_matrix(swot_report) -> List[dict]:
    """
    Build the Importance-Performance matrix from SWOT items.

    Useful for dashboards visualizing where to focus resources.

    Returns:
        List of dicts with item info + PI zone
    """
    matrix = []

    for quadrant_name in ("strengths", "weaknesses", "opportunities", "threats"):
        items = getattr(swot_report, quadrant_name, [])
        for item in items:
            zone = compute_pi_zone(
                performance_score=item.scoring.performance_score,
                importance=item.scoring.importance,
            )
            item.pi_zone = zone

            matrix.append({
                "item_id": item.item_id,
                "title": item.title,
                "quadrant": quadrant_name,
                "importance": item.scoring.importance,
                "performance": item.scoring.performance_score,
                "zone": zone,
            })

    return matrix


def build_vulnerability_matrix(swot_report) -> List[dict]:
    """
    Build vulnerability matrix focusing on weaknesses and threats.

    Returns:
        List of dicts with vulnerability scores
    """
    matrix = []

    # Weaknesses and threats are most vulnerable
    for quadrant_name in ("weaknesses", "threats"):
        items = getattr(swot_report, quadrant_name, [])
        for item in items:
            vuln = compute_vulnerability_score(
                confidence=item.scoring.confidence,
                performance_score=item.scoring.performance_score,
                importance=item.scoring.importance,
            )
            item.vulnerability_score = vuln

            matrix.append({
                "item_id": item.item_id,
                "title": item.title,
                "quadrant": quadrant_name,
                "vulnerability_score": vuln,
                "importance": item.scoring.importance,
                "confidence": item.scoring.confidence,
            })

    # Sort by vulnerability (descending)
    matrix.sort(key=lambda x: x["vulnerability_score"], reverse=True)
    return matrix


def build_opportunity_threat_matrix(swot_report) -> List[dict]:
    """
    Build a focused matrix on external factors (opportunities + threats).

    Returns:
        List of dicts with priority info
    """
    matrix = []

    for quadrant_name in ("opportunities", "threats"):
        items = getattr(swot_report, quadrant_name, [])
        for item in items:
            matrix.append({
                "item_id": item.item_id,
                "title": item.title,
                "quadrant": quadrant_name,
                "strategic_priority": item.scoring.strategic_priority,
                "claim_strength": item.claim_strength,
            })

    matrix.sort(key=lambda x: x["strategic_priority"], reverse=True)
    return matrix


def enrich_with_matrices(swot_report) -> dict:
    """
    Enrich SWOT report with all 3 matrix outputs.

    Returns:
        Dict with 3 matrices:
        - importance_performance_matrix
        - opportunity_threat_matrix
        - vulnerability_matrix
    """
    matrices = {
        "importance_performance_matrix": build_importance_performance_matrix(swot_report),
        "opportunity_threat_matrix": build_opportunity_threat_matrix(swot_report),
        "vulnerability_matrix": build_vulnerability_matrix(swot_report),
    }

    logger.info(
        f"[PostProcessor] Built matrices: "
        f"PI={len(matrices['importance_performance_matrix'])}, "
        f"OT={len(matrices['opportunity_threat_matrix'])}, "
        f"Vuln={len(matrices['vulnerability_matrix'])}"
    )

    return matrices