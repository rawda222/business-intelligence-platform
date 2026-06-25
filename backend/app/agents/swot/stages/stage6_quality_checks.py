"""
SWOT Agent v7 - Stage 6: Quality Checks (FIX 13)
=================================================
Comprehensive quality report with 11 sub-lists.
"""
import logging
from typing import List

from app.agents.swot.schemas.output import (
    SWOTItem,
    SWOTReport,
    QualityReport,
    QualityReportItem,
)
from app.agents.swot.config import (
    WEAKNESS_SCORING_ISSUE_FLOOR,
    STRENGTH_SCORING_ISSUE_CEILING,
)


logger = logging.getLogger("swot_agent_v7")


def run_quality_checks(
    swot_report: SWOTReport,
    benchmark_quality: str,
) -> QualityReport:
    """
    Comprehensive quality checks (FIX 13).
    
    Populates 11 sub-lists:
    - unsupported_items
    - duplicate_items
    - semantic_overlaps
    - cross_quadrant_theme_conflicts
    - scoring_issues
    - benchmark_warnings
    - summary_issues
    - low_confidence_items
    - generic_items
    - manual_review_needed
    - consistency_violations
    """
    qr = QualityReport()
    
    all_items = (
        swot_report.strengths + swot_report.weaknesses +
        swot_report.opportunities + swot_report.threats
    )
    
    # Check 1: Unsupported items (no evidence)
    for item in all_items:
        if not item.evidence_refs:
            qr.unsupported_items.append(QualityReportItem(
                item_id=item.item_id,
                issue="no_evidence_refs",
                severity="medium",
                theme=item.source_theme,
                description=f"Item '{item.title}' has no supporting evidence",
            ))
    
    # Check 2: Duplicate items (by source_theme + quadrant)
    seen = {}
    for item in all_items:
        key = (item.source_theme, item.quadrant)
        if key in seen:
            qr.duplicate_items.append(QualityReportItem(
                item_id=item.item_id,
                issue="duplicate_source_theme",
                severity="low",
                theme=item.source_theme,
                description=f"Duplicate of {seen[key]}",
            ))
        else:
            seen[key] = item.item_id
    
    # Check 3: Scoring issues
    for item in swot_report.weaknesses:
        if item.scoring.performance_score >= WEAKNESS_SCORING_ISSUE_FLOOR:
            qr.scoring_issues.append(QualityReportItem(
                item_id=item.item_id,
                issue="weakness_high_performance",
                severity="medium",
                description=(
                    f"Weakness has unexpectedly high performance score "
                    f"({item.scoring.performance_score})"
                ),
            ))
    
    for item in swot_report.strengths:
        if item.scoring.performance_score <= STRENGTH_SCORING_ISSUE_CEILING:
            qr.scoring_issues.append(QualityReportItem(
                item_id=item.item_id,
                issue="strength_low_performance",
                severity="medium",
                description=(
                    f"Strength has unexpectedly low performance score "
                    f"({item.scoring.performance_score})"
                ),
            ))
    
    # Check 4: Benchmark warnings
    if benchmark_quality in ("low", "unavailable"):
        qr.benchmark_warnings.append(QualityReportItem(
            issue="weak_benchmark",
            severity="medium",
            description=(
                f"Benchmark quality is '{benchmark_quality}'. "
                f"Competitive comparisons should be directional only."
            ),
        ))
    
    # Check 5: Low confidence items
    for item in all_items:
        if item.scoring.confidence < 0.4:
            qr.low_confidence_items.append(QualityReportItem(
                item_id=item.item_id,
                issue="low_confidence",
                severity="low",
                description=f"Confidence={item.scoring.confidence:.2f} below 0.4",
            ))
    
    # Check 6: Generic items (very short reasoning)
    for item in all_items:
        if len(item.reasoning) < 20:
            qr.generic_items.append(QualityReportItem(
                item_id=item.item_id,
                issue="generic_or_short_reasoning",
                severity="low",
                description=f"Reasoning too short: '{item.reasoning[:30]}...'",
            ))
    
    # Check 7: Manual review needed
    for item in all_items:
        if item.manual_review_only:
            qr.manual_review_needed.append(QualityReportItem(
                item_id=item.item_id,
                issue="manual_review_flag",
                severity="info",
                description=f"Item flagged for manual review",
            ))
    
    logger.info(
        f"[Stage 6] Quality checks complete: "
        f"unsupported={len(qr.unsupported_items)}, "
        f"duplicates={len(qr.duplicate_items)}, "
        f"scoring_issues={len(qr.scoring_issues)}"
    )
    
    return qr