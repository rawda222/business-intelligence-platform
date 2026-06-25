"""
SWOT Agent v7 - Stage 9: Cross-Quadrant Deduplication (FIX 6)
=============================================================
Detect semantic overlaps and cross-quadrant conflicts.
"""
import logging
import re

from app.agents.swot.config import STOP_TOKENS


logger = logging.getLogger("swot_agent_v7")


def detect_semantic_overlaps(swot_report, quality_report):
    """
    Detect semantic overlaps and cross-quadrant conflicts (FIX 6).

    Same theme should not appear in both strengths and weaknesses unless
    the LLM provided explicit reasoning.
    """
    all_items = []
    for quadrant in ("strengths", "weaknesses", "opportunities", "threats"):
        for item in getattr(swot_report, quadrant):
            all_items.append((quadrant, item))

    # Group by source_theme
    by_theme = {}
    for quadrant, item in all_items:
        if item.source_theme not in by_theme:
            by_theme[item.source_theme] = []
        by_theme[item.source_theme].append((quadrant, item))

    # Check for cross-quadrant conflicts
    for theme, items in by_theme.items():
        if len(items) < 2:
            continue

        quadrants_seen = {q for q, _ in items}

        # Strength + Weakness on same theme = conflict
        if "strengths" in quadrants_seen and "weaknesses" in quadrants_seen:
            from app.agents.swot.schemas.output import QualityReportItem
            quality_report.cross_quadrant_theme_conflicts.append(
                QualityReportItem(
                    issue="strength_and_weakness_same_theme",
                    severity="medium",
                    theme=theme,
                    description=(
                        f"Theme '{theme}' appears in both strengths and weaknesses"
                    ),
                )
            )
            logger.warning(
                f"[Stage 9] Cross-quadrant conflict on theme '{theme}'"
            )

        # Opportunity + Threat on same theme = conflict
        if "opportunities" in quadrants_seen and "threats" in quadrants_seen:
            from app.agents.swot.schemas.output import QualityReportItem
            quality_report.cross_quadrant_theme_conflicts.append(
                QualityReportItem(
                    issue="opportunity_and_threat_same_theme",
                    severity="medium",
                    theme=theme,
                    description=(
                        f"Theme '{theme}' appears in both opportunities and threats"
                    ),
                )
            )

    # Detect semantic overlaps within same quadrant
    for quadrant_name in ("strengths", "weaknesses", "opportunities", "threats"):
        items = getattr(swot_report, quadrant_name)
        for i, item1 in enumerate(items):
            tokens1 = _tokenize_concept(item1.title)
            for item2 in items[i + 1:]:
                tokens2 = _tokenize_concept(item2.title)
                overlap = tokens1 & tokens2
                if len(overlap) >= 3:
                    from app.agents.swot.schemas.output import QualityReportItem
                    quality_report.semantic_overlaps.append(
                        QualityReportItem(
                            issue="semantic_overlap",
                            severity="low",
                            description=(
                                f"Items '{item1.title}' and '{item2.title}' "
                                f"share concepts: {overlap}"
                            ),
                        )
                    )

    logger.info(
        f"[Stage 9] Dedup checks complete: "
        f"conflicts={len(quality_report.cross_quadrant_theme_conflicts)}, "
        f"overlaps={len(quality_report.semantic_overlaps)}"
    )


def _tokenize_concept(text):
    """Tokenize text into normalized concept tokens (FIX 8 helper)."""
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return {t for t in tokens if t not in STOP_TOKENS and len(t) > 2}
