"""
SWOT Agent v7 - Stage 7: Strategic Summary (FIX 10/12)
=======================================================
Build the top-level strategic summary with disambiguated fields.
"""
import logging

from app.agents.swot.schemas.output import (
    SWOTReport,
    StrategicSummary,
    WatchoutItem,
    DerivedOpportunity,
    DirectionalCompetitiveSignal,
)


logger = logging.getLogger("swot_agent_v7")


def build_strategic_summary(
    swot_report,
    watchouts,
    derived_opportunities,
    directional_signals,
    benchmark_quality,
):
    """
    Build top-level summary with disambiguated fields (FIX 10/12).

    Uses cautious language when benchmark_quality is low.
    """
    summary = StrategicSummary()

    is_low_benchmark = benchmark_quality in ("low", "unavailable")

    # Top strength
    if swot_report.strengths:
        top = max(
            swot_report.strengths,
            key=lambda x: x.scoring.strategic_priority,
        )
        summary.top_strength = top.title
        summary.main_advantage = (
            f"Strongest area: {top.title}"
            if not is_low_benchmark
            else f"Internal strength observed: {top.title}"
        )

    # Top confirmed weakness
    if swot_report.weaknesses:
        top = max(
            swot_report.weaknesses,
            key=lambda x: x.scoring.strategic_priority,
        )
        summary.top_confirmed_weakness = top.title

    # Top watchout
    if watchouts:
        summary.top_watchout = watchouts[0].title

    # Top opportunity
    if swot_report.opportunities:
        top = max(
            swot_report.opportunities,
            key=lambda x: x.scoring.strategic_priority,
        )
        summary.top_opportunity = top.title
        summary.best_growth_opportunity = (
            f"Best growth area: {top.title}"
            if not is_low_benchmark
            else f"Possible growth direction: {top.title}"
        )

    # Top derived opportunity
    if derived_opportunities:
        summary.top_derived_opportunity = derived_opportunities[0].title

    # Top confirmed threat
    if swot_report.threats:
        top = max(
            swot_report.threats,
            key=lambda x: x.scoring.strategic_priority,
        )
        summary.top_confirmed_threat = top.title
        summary.most_critical_risk = (
            f"Critical risk: {top.title}"
            if not is_low_benchmark
            else f"Potential concern: {top.title}"
        )

    # Top directional threat
    if directional_signals:
        threats = [s for s in directional_signals if s.direction == "disadvantage"]
        if threats:
            summary.top_directional_threat = threats[0].title

    logger.info("[Stage 7] Strategic summary built")
    return summary