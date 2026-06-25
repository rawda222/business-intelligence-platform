"""
SWOT Agent v7 - Stage 8: Competitive Signals (FIX 4/9)
=======================================================
Build directional competitive signals and derived opportunities.
"""
import logging

from app.agents.swot.schemas.output import (
    DerivedOpportunity,
    DirectionalCompetitiveSignal,
    EvidenceSummary,
    SWOTScoring,
)
from app.agents.swot.enums import ClaimStrength
from app.agents.swot.utils.slugify import slugify


logger = logging.getLogger("swot_agent_v7")


def build_directional_signals(
    themes,
    benchmark_quality,
    competitor_review_counts,
):
    """
    Build directional competitive signals (FIX 4).

    When benchmark quality is low, comparisons should be directional only.
    """
    signals = []

    if benchmark_quality not in ("low", "unavailable"):
        return signals

    for theme in themes:
        if theme.entity_type != "comparative":
            continue

        if theme.performance_gap is None:
            continue

        if abs(theme.performance_gap) < 0.10:
            continue

        direction = "advantage" if theme.performance_gap > 0 else "disadvantage"

        signal = DirectionalCompetitiveSignal(
            signal_id=f"DS_{slugify(theme.theme_category)}",
            title=(
                f"Directional {direction}: "
                f"{theme.theme_category.replace('_', ' ').title()}"
            ),
            reasoning=(
                f"Performance gap detected (gap={theme.performance_gap:.2f}). "
                f"Benchmark quality is '{benchmark_quality}', so this is directional only."
            ),
            direction=direction,
            source_theme=theme.theme_category,
            benchmark_quality=benchmark_quality,
            competitor_review_counts=competitor_review_counts,
            claim_strength=ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value,
            should_feed_strategy_agent=True,
            should_feed_campaign_planner=False,
            manual_review_only=True,
            evidence_refs=theme.evidence_refs[:5],
            evidence_summary=EvidenceSummary(
                source_mentions=theme.frequency,
                source_frequency=theme.frequency,
                available_evidence_refs=len(theme.evidence_refs),
                displayed_evidence_refs=min(5, len(theme.evidence_refs)),
            ),
            low_benchmark_quality=True,
        )
        signals.append(signal)

    logger.info(f"[Stage 8] Built {len(signals)} directional signals")
    return signals


def build_derived_opportunities(strengths):
    """
    Build derived opportunities from strengths (FIX 9).

    For each strong area, suggest extending/leveraging it.
    """
    derived = []

    for s in strengths:
        if s.scoring.strategic_priority < 6.0:
            continue

        opp = DerivedOpportunity(
            item_id=f"DO_{slugify(s.title)}",
            title=f"Leverage: {s.title}",
            reasoning=(
                f"Build on existing strength '{s.title}' to drive growth. "
                f"This strength has high strategic priority "
                f"({s.scoring.strategic_priority:.1f})."
            ),
            opportunity_type="strength_extension",
            derived_from=[s.item_id],
            parent_theme=s.source_theme,
            source_theme=s.source_theme,
            claim_strength=ClaimStrength.INTERNALLY_SUPPORTED.value,
            recommended_strategy_type="SO",
            evidence_refs=s.evidence_refs,
            evidence_summary=s.evidence_summary,
            scoring=SWOTScoring(
                importance=s.scoring.importance,
                impact=s.scoring.impact,
                confidence=min(1.0, s.scoring.confidence + 0.1),
                frequency_norm=s.scoring.frequency_norm,
                performance_score=s.scoring.performance_score,
                strategic_priority=s.scoring.strategic_priority * 0.9,
            ),
            should_feed_strategy_agent=True,
            should_feed_campaign_planner=True,
            manual_review_only=False,
            low_benchmark_quality=s.low_benchmark_quality,
        )
        derived.append(opp)

    logger.info(f"[Stage 8] Built {len(derived)} derived opportunities")
    return derived