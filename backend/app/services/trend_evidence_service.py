"""
Trend Evidence Service

Converts BusinessTrendReport and deterministic TrendInsight objects
into structured evidence entries.

Evidence entries are downstream-friendly for:

- SWOT synthesis.
- Strategy generation.
- AI reasoning that must cite factual signals only.

Every evidence entry is Business-scoped and derived from either a
known insight or a numeric metric present in the report. There is
no forecasting, no clustering, and no AI at this stage.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.services.business_trend_report_service import (
    BusinessTrendReport,
)
from app.services.trend_insight_service import (
    TrendInsight,
)


# ============================================================
# Public Enums
# ============================================================
EvidenceCategory = Literal[
    "publishing",
    "reviews",
    "engagement",
]


EvidenceDirection = Literal[
    "positive",
    "neutral",
    "negative",
]


# ============================================================
# Evidence Entry
# ============================================================
@dataclass(slots=True)
class TrendEvidence:
    """One structured evidence entry."""

    category: EvidenceCategory

    direction: EvidenceDirection

    confidence: float

    metric: str

    value: float | int | str

    reference: str

    description: str

    supporting_metrics: dict[
        str,
        float | int | str,
    ] = field(
        default_factory=dict,
    )


# ============================================================
# Helpers
# ============================================================
def _direction_from_severity(
    severity: str,
) -> EvidenceDirection:
    """Map insight severity to evidence direction."""

    if severity == "warning":
        return "negative"

    return "positive"


def _insight_evidence(
    insight: TrendInsight,
    *,
    category: EvidenceCategory,
    confidence: float,
    metric: str,
    value: float | int | str,
    supporting_metrics: (
        dict[
            str,
            float | int | str,
        ]
        | None
    ) = None,
) -> TrendEvidence:
    """Build an evidence entry derived from an insight."""

    return TrendEvidence(
        category=category,
        direction=(
            _direction_from_severity(
                insight.severity,
            )
        ),
        confidence=confidence,
        metric=metric,
        value=value,
        reference=(
            f"insight:{insight.code}"
        ),
        description=insight.message,
        supporting_metrics=(
            supporting_metrics or {}
        ),
    )


# ============================================================
# Evidence Builders
# ============================================================
def _publishing_evidence(
    report: BusinessTrendReport,
    insights: list[TrendInsight],
) -> list[
    TrendEvidence
]:
    """Build publishing-related evidence."""

    evidence: list[TrendEvidence] = []

    publishing_activity = next(
        (
            insight
            for insight in insights
            if insight.code
            == "publishing_activity"
        ),
        None,
    )

    if publishing_activity is not None:
        total_posts = (
            report.posts_per_week.total_posts
        )

        evidence.append(
            _insight_evidence(
                publishing_activity,
                category="publishing",
                confidence=0.9,
                metric="total_posts",
                value=total_posts,
            )
        )

    publishing_trend = next(
        (
            insight
            for insight in insights
            if insight.code
            == "publishing_trend"
        ),
        None,
    )

    if publishing_trend is not None:
        supporting = (
            publishing_trend.evidence
        )

        evidence.append(
            _insight_evidence(
                publishing_trend,
                category="publishing",
                confidence=0.7,
                metric=(
                    "publishing_trend_"
                    "direction"
                ),
                value=(
                    publishing_trend
                    .severity
                ),
                supporting_metrics=(
                    supporting
                ),
            )
        )

    return evidence


def _review_evidence(
    report: BusinessTrendReport,
    insights: list[TrendInsight],
) -> list[
    TrendEvidence
]:
    """Build customer-review evidence."""

    evidence: list[TrendEvidence] = []

    review_volume = next(
        (
            insight
            for insight in insights
            if insight.code
            == "review_volume"
        ),
        None,
    )

    if review_volume is not None:
        total_reviews = (
            report.reviews_per_month
            .total_reviews
        )

        evidence.append(
            _insight_evidence(
                review_volume,
                category="reviews",
                confidence=0.9,
                metric="total_reviews",
                value=total_reviews,
            )
        )

    rating_direction = next(
        (
            insight
            for insight in insights
            if insight.code
            == "rating_direction"
        ),
        None,
    )

    if rating_direction is not None:
        supporting = (
            rating_direction.evidence
        )

        evidence.append(
            _insight_evidence(
                rating_direction,
                category="reviews",
                confidence=0.6,
                metric=(
                    "rating_average_"
                    "direction"
                ),
                value=(
                    rating_direction
                    .severity
                ),
                supporting_metrics=(
                    supporting
                ),
            )
        )

    return evidence


def _engagement_evidence(
    report: BusinessTrendReport,
) -> list[
    TrendEvidence
]:
    """Build engagement evidence from raw curves."""

    evidence: list[TrendEvidence] = []

    curves = report.engagement_curves

    if not curves:
        return evidence

    max_reactions = 0

    for curve in curves:
        for point in curve.points:
            reactions = point.reactions

            if (
                reactions is not None
                and reactions > max_reactions
            ):
                max_reactions = reactions

    if max_reactions == 0:
        return evidence

    evidence.append(
        TrendEvidence(
            category="engagement",
            direction="neutral",
            confidence=0.5,
            metric=(
                "peak_reactions_"
                "observed"
            ),
            value=max_reactions,
            reference=(
                "engagement_curves"
            ),
            description=(
                "Peak reactions observed "
                "across analyzed posts."
            ),
        )
    )

    return evidence


# ============================================================
# Public Entry Point
# ============================================================
def build_trend_evidence(
    *,
    report: BusinessTrendReport,
    insights: list[TrendInsight],
) -> list[
    TrendEvidence
]:
    """
    Build ordered evidence entries from a report and its insights.
    """

    evidence: list[TrendEvidence] = []

    evidence.extend(
        _publishing_evidence(
            report=report,
            insights=insights,
        )
    )

    evidence.extend(
        _review_evidence(
            report=report,
            insights=insights,
        )
    )

    evidence.extend(
        _engagement_evidence(
            report=report,
        )
    )

    return evidence