"""
Trend Insight Service

Converts a BusinessTrendReport into a compact list of insight
statements that downstream layers (SWOT, Strategy, UI) can use.

The current stage uses only explicit deterministic rules. No AI,
no forecasting, and no trend calculations beyond what the report
already exposes.

An insight is only produced when the report contains enough data
for the rule to fire.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.business_trend_report_service import (
    BusinessTrendReport,
)


# ============================================================
# Insight Types
# ============================================================
InsightSeverity = Literal[
    "info",
    "warning",
]


InsightCode = Literal[
    "publishing_activity",
    "publishing_trend",
    "rating_direction",
    "review_volume",
]


@dataclass(slots=True)
class TrendInsight:
    """One deterministic insight derived from a trend report."""

    code: InsightCode

    severity: InsightSeverity

    message: str

    evidence: dict[str, float | int | str]


# ============================================================
# Rule Helpers
# ============================================================
def _split_buckets_in_half(
    buckets,
):
    """Split ordered buckets into first and second halves."""

    if len(buckets) == 0:
        return [], []

    midpoint = len(buckets) // 2

    if midpoint == 0:
        midpoint = 1

    first_half = buckets[:midpoint]
    second_half = buckets[midpoint:]

    return first_half, second_half


def _sum_post_counts(buckets) -> int:
    return sum(
        bucket.post_count
        for bucket in buckets
    )


def _first_bucket_with_rating(buckets):
    for bucket in buckets:
        if bucket.rating_average is not None:
            return bucket

    return None


def _last_bucket_with_rating(buckets):
    for bucket in reversed(buckets):
        if bucket.rating_average is not None:
            return bucket

    return None


# ============================================================
# Rule Implementations
# ============================================================
def _publishing_activity_insight(
    report: BusinessTrendReport,
) -> TrendInsight | None:
    total_posts = (
        report.posts_per_week.total_posts
    )

    if total_posts > 0:
        return TrendInsight(
            code="publishing_activity",
            severity="info",
            message=(
                "The business published "
                f"{total_posts} posts "
                "in the selected range."
            ),
            evidence={
                "total_posts": total_posts,
            },
        )

    return TrendInsight(
        code="publishing_activity",
        severity="warning",
        message=(
            "No posts were published in the "
            "selected range."
        ),
        evidence={
            "total_posts": 0,
        },
    )


def _publishing_trend_insight(
    report: BusinessTrendReport,
) -> TrendInsight | None:
    buckets = report.posts_per_week.buckets

    if len(buckets) < 2:
        return None

    first_half, second_half = (
        _split_buckets_in_half(
            buckets,
        )
    )

    first_total = _sum_post_counts(
        first_half,
    )

    second_total = _sum_post_counts(
        second_half,
    )

    if first_total == 0 and second_total == 0:
        return None

    if second_total > first_total:
        return TrendInsight(
            code="publishing_trend",
            severity="info",
            message=(
                "Publishing activity increased "
                "in the second half of the "
                "selected range."
            ),
            evidence={
                "first_half_posts": (
                    first_total
                ),
                "second_half_posts": (
                    second_total
                ),
            },
        )

    if second_total < first_total:
        return TrendInsight(
            code="publishing_trend",
            severity="warning",
            message=(
                "Publishing activity decreased "
                "in the second half of the "
                "selected range."
            ),
            evidence={
                "first_half_posts": (
                    first_total
                ),
                "second_half_posts": (
                    second_total
                ),
            },
        )

    return TrendInsight(
        code="publishing_trend",
        severity="info",
        message=(
            "Publishing activity remained "
            "stable across the selected range."
        ),
        evidence={
            "first_half_posts": first_total,
            "second_half_posts": second_total,
        },
    )


def _rating_direction_insight(
    report: BusinessTrendReport,
) -> TrendInsight | None:
    buckets = report.reviews_per_month.buckets

    first_bucket = _first_bucket_with_rating(
        buckets,
    )

    last_bucket = _last_bucket_with_rating(
        buckets,
    )

    if (
        first_bucket is None
        or last_bucket is None
    ):
        return None

    if (
        first_bucket.month_start
        == last_bucket.month_start
    ):
        return None

    first_average = first_bucket.rating_average
    last_average = last_bucket.rating_average

    if last_average > first_average:
        return TrendInsight(
            code="rating_direction",
            severity="info",
            message=(
                "Rating average improved between "
                f"{first_bucket.month_start} "
                "and "
                f"{last_bucket.month_start}."
            ),
            evidence={
                "first_month_rating_average": (
                    first_average
                ),
                "last_month_rating_average": (
                    last_average
                ),
            },
        )

    if last_average < first_average:
        return TrendInsight(
            code="rating_direction",
            severity="warning",
            message=(
                "Rating average declined between "
                f"{first_bucket.month_start} "
                "and "
                f"{last_bucket.month_start}."
            ),
            evidence={
                "first_month_rating_average": (
                    first_average
                ),
                "last_month_rating_average": (
                    last_average
                ),
            },
        )

    return None


def _review_volume_insight(
    report: BusinessTrendReport,
) -> TrendInsight | None:
    total_reviews = (
        report.reviews_per_month.total_reviews
    )

    if total_reviews == 0:
        return TrendInsight(
            code="review_volume",
            severity="warning",
            message=(
                "No customer reviews found in "
                "the selected range."
            ),
            evidence={
                "total_reviews": 0,
            },
        )

    if total_reviews < 5:
        return TrendInsight(
            code="review_volume",
            severity="warning",
            message=(
                "Review volume is low. Fewer "
                f"than 5 reviews were captured "
                "in the selected range."
            ),
            evidence={
                "total_reviews": (
                    total_reviews
                ),
            },
        )

    return TrendInsight(
        code="review_volume",
        severity="info",
        message=(
            f"{total_reviews} reviews were "
            "captured in the selected range."
        ),
        evidence={
            "total_reviews": total_reviews,
        },
    )


# ============================================================
# Public Entry Point
# ============================================================
def build_trend_insights(
    report: BusinessTrendReport,
) -> list[
    TrendInsight
]:
    """
    Build the ordered list of deterministic insights for one report.

    Insights that require data not present in the report are simply
    not emitted.
    """

    insights: list[
        TrendInsight
    ] = []

    for rule in (
        _publishing_activity_insight,
        _publishing_trend_insight,
        _rating_direction_insight,
        _review_volume_insight,
    ):
        insight = rule(report)

        if insight is not None:
            insights.append(insight)

    return insights