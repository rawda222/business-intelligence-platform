"""
SWOT Agent v7 - Stage 3: Rule-Based Fallback
=============================================
Deterministic SWOT generator used when all LLM providers fail.
"""
import logging
from typing import List

from app.agents.swot.schemas.input import BusinessProfile, ReviewTheme
from app.agents.swot.schemas.llm import (
    LLMSWOTOutput,
    LLMSWOTReport,
    LLMSWOTItem,
    LLMStrategicSummary,
    LLMScoring,
)
from app.agents.swot.config import (
    POSITIVE_RATIO_STRENGTH,
    NEGATIVE_RATIO_WEAKNESS,
)


logger = logging.getLogger("swot_agent_v7")


def generate_rule_based_swot(
    profile: BusinessProfile,
    benchmark_quality: str,
) -> LLMSWOTOutput:
    """
    Deterministic SWOT generator - used as fallback if all LLM providers fail.
    
    Logic:
    - Strengths: themes with positive ratio >= 0.70
    - Weaknesses: themes with negative ratio >= 0.35
    - Opportunities: comparative themes where target > competitor
    - Threats: comparative themes where target < competitor
    """
    logger.info("[Stage 3] Generating rule-based SWOT fallback")
    
    strengths: List[LLMSWOTItem] = []
    weaknesses: List[LLMSWOTItem] = []
    opportunities: List[LLMSWOTItem] = []
    threats: List[LLMSWOTItem] = []
    
    for theme in profile.themes:
        sb = theme.sentiment_balance
        total = sb.total
        
        if total == 0:
            continue
        
        pos_ratio = sb.positive / total
        neg_ratio = sb.negative / total
        
        # Strength check
        if pos_ratio >= POSITIVE_RATIO_STRENGTH and theme.entity_type == "target_business":
            strengths.append(_make_item(
                theme=theme,
                quadrant="strengths",
                title=f"Strong {theme.theme_category.replace('_', ' ').title()}",
                reasoning=f"Theme '{theme.theme_category}' shows high positive sentiment "
                         f"({sb.positive}/{total} = {pos_ratio:.1%}).",
            ))
        
        # Weakness check
        elif neg_ratio >= NEGATIVE_RATIO_WEAKNESS and theme.entity_type == "target_business":
            weaknesses.append(_make_item(
                theme=theme,
                quadrant="weaknesses",
                title=f"Weakness in {theme.theme_category.replace('_', ' ').title()}",
                reasoning=f"Theme '{theme.theme_category}' shows significant negative sentiment "
                         f"({sb.negative}/{total} = {neg_ratio:.1%}).",
            ))
        
        # Opportunity / Threat from comparison
        if theme.entity_type == "comparative" and theme.performance_gap is not None:
            if theme.performance_gap > 0.15:
                opportunities.append(_make_item(
                    theme=theme,
                    quadrant="opportunities",
                    title=f"Advantage in {theme.theme_category.replace('_', ' ').title()}",
                    reasoning=f"Target outperforms competitors in '{theme.theme_category}' "
                             f"(gap={theme.performance_gap:.2f}).",
                ))
            elif theme.performance_gap < -0.15:
                threats.append(_make_item(
                    theme=theme,
                    quadrant="threats",
                    title=f"Competitive Gap in {theme.theme_category.replace('_', ' ').title()}",
                    reasoning=f"Target underperforms in '{theme.theme_category}' "
                             f"(gap={theme.performance_gap:.2f}).",
                ))
    
    # Strategic summary
    summary = LLMStrategicSummary()
    if strengths:
        summary.main_advantage = strengths[0].title
    if threats:
        summary.most_critical_risk = threats[0].title
    if opportunities:
        summary.best_growth_opportunity = opportunities[0].title
    
    logger.info(
        f"[Stage 3] Rule-based output: "
        f"S={len(strengths)}, W={len(weaknesses)}, "
        f"O={len(opportunities)}, T={len(threats)}"
    )
    
    return LLMSWOTOutput(
        swot_report=LLMSWOTReport(
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
        ),
        strategic_summary=summary,
    )


def _make_item(
    theme: ReviewTheme,
    quadrant: str,
    title: str,
    reasoning: str,
) -> LLMSWOTItem:
    """Build a simple LLM SWOT item from a theme."""
    return LLMSWOTItem(
        title=title,
        reasoning=reasoning,
        source_theme=theme.theme_category,
        quadrant=quadrant,
        tags=[],
        scoring=LLMScoring(
            importance=6.0,
            impact=6.0,
            confidence=0.5,
        ),
        evidence_refs=theme.evidence_refs[:5],
        frequency=theme.frequency,
    )