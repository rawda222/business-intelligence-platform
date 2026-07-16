"""
Trend Evidence Service Tests

Verifies deterministic evidence generation from trend reports and
insights without touching MongoDB or PostgreSQL.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.services.business_trend_report_service import (
    BusinessTrendReport,
)
from app.services.post_engagement_curve_service import (
    PostEngagementCurve,
    PostEngagementCurvePoint,
)
from app.services.post_trend_service import (
    PostsPerWeekBucket,
    PostsPerWeekTrend,
)
from app.services.review_trend_service import (
    ReviewsPerMonthBucket,
    ReviewsPerMonthTrend,
)
from app.services.trend_evidence_service import (
    build_trend_evidence,
)
from app.services.trend_foundation_service import (
    BusinessTrendFoundationStats,
)
from app.services.trend_insight_service import (
    TrendInsight,
    build_trend_insights,
)


def _make_report(
    *,
    total_posts: int,
    weekly_counts,
    monthly_ratings,
    monthly_review_counts,
    engagement_reactions: int | None,
) -> BusinessTrendReport:
    """Build a synthetic BusinessTrendReport for evidence testing."""

    business_id = uuid4()
    social_account_id = uuid4()

    range_start = datetime(
        2026,
        6,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    range_end = datetime(
        2026,
        9,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    foundation = (
        BusinessTrendFoundationStats(
            business_id=business_id,
            total_posts=total_posts,
            total_post_metric_snapshots=0,
            total_comments=0,
            total_customer_reviews=(
                sum(monthly_review_counts)
            ),
            posts_by_platform={},
            comments_by_platform={},
            reviews_by_source={},
        )
    )

    week_buckets = [
        PostsPerWeekBucket(
            week_start=date(
                2026,
                7,
                6,
            ),
            post_count=count,
        )
        for count in weekly_counts
    ]

    posts_per_week = PostsPerWeekTrend(
        business_id=business_id,
        range_start=range_start,
        range_end=range_end,
        buckets=week_buckets,
        total_posts=total_posts,
    )

    months = [
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
    ]

    month_buckets = []

    for index, month in enumerate(months):
        month_buckets.append(
            ReviewsPerMonthBucket(
                month_start=month,
                review_count=(
                    monthly_review_counts[
                        index
                    ]
                ),
                meaningful_review_count=(
                    monthly_review_counts[
                        index
                    ]
                ),
                rating_average=(
                    monthly_ratings[index]
                ),
            )
        )

    reviews_per_month = (
        ReviewsPerMonthTrend(
            business_id=business_id,
            source="google_maps",
            range_start=range_start,
            range_end=range_end,
            buckets=month_buckets,
            total_reviews=(
                sum(monthly_review_counts)
            ),
            total_meaningful_reviews=(
                sum(monthly_review_counts)
            ),
        )
    )

    engagement_curves = []

    if engagement_reactions is not None:
        engagement_curves.append(
            PostEngagementCurve(
                business_id=business_id,
                social_account_id=(
                    social_account_id
                ),
                social_post_id=uuid4(),
                range_start=range_start,
                range_end=range_end,
                points=[
                    PostEngagementCurvePoint(
                        day=date(
                            2026,
                            7,
                            8,
                        ),
                        captured_at=(
                            datetime(
                                2026,
                                7,
                                8,
                                18,
                                0,
                                tzinfo=UTC,
                            )
                        ),
                        likes=None,
                        reactions=(
                            engagement_reactions
                        ),
                        comments=1,
                        shares=0,
                        views=100,
                    ),
                ],
            )
        )

    return BusinessTrendReport(
        business_id=business_id,
        range_start=range_start,
        range_end=range_end,
        review_source="google_maps",
        foundation=foundation,
        posts_per_week=posts_per_week,
        reviews_per_month=(
            reviews_per_month
        ),
        engagement_curves=engagement_curves,
    )


def test_evidence_is_built_for_active_business():
    """When activity exists, evidence should reflect it."""

    report = _make_report(
        total_posts=8,
        weekly_counts=[
            4,
            3,
            1,
            1,
        ],
        monthly_ratings=[3.5, None, 4.5],
        monthly_review_counts=[2, 2, 2],
        engagement_reactions=25,
    )

    insights = build_trend_insights(
        report=report,
    )

    evidence = build_trend_evidence(
        report=report,
        insights=insights,
    )

    categories = {
        entry.category
        for entry in evidence
    }

    assert (
        "publishing" in categories
    )

    assert (
        "reviews" in categories
    )

    assert (
        "engagement" in categories
    )

    engagement_entry = next(
        entry
        for entry in evidence
        if entry.category == "engagement"
    )

    assert engagement_entry.value == 25

    publishing_activity_entry = next(
        entry
        for entry in evidence
        if (
            entry.metric
            == "total_posts"
        )
    )

    assert (
        publishing_activity_entry.direction
        == "positive"
    )


def test_evidence_reflects_declining_activity_and_low_reviews():
    """Warnings should map to negative evidence."""

    report = _make_report(
        total_posts=6,
        weekly_counts=[
            4,
            3,
            1,
            1,
        ],
        monthly_ratings=[4.5, None, 3.5],
        monthly_review_counts=[2, 1, 0],
        engagement_reactions=None,
    )

    insights = build_trend_insights(
        report=report,
    )

    evidence = build_trend_evidence(
        report=report,
        insights=insights,
    )

    publishing_trend_entry = next(
        entry
        for entry in evidence
        if (
            entry.metric
            == "publishing_trend_direction"
        )
    )

    assert (
        publishing_trend_entry.direction
        == "negative"
    )

    reviews_entry = next(
        entry
        for entry in evidence
        if (
            entry.metric
            == "rating_average_direction"
        )
    )

    assert (
        reviews_entry.direction
        == "negative"
    )

    review_volume_entry = next(
        entry
        for entry in evidence
        if entry.metric == "total_reviews"
    )

    assert (
        review_volume_entry.direction
        == "negative"
    )


def test_empty_report_produces_empty_engagement_but_still_warnings():
    """
    Even with no activity, publishing/reviews warnings should still
    produce evidence entries.
    """

    report = _make_report(
        total_posts=0,
        weekly_counts=[
            0,
            0,
        ],
        monthly_ratings=[None, None, None],
        monthly_review_counts=[0, 0, 0],
        engagement_reactions=None,
    )

    insights = build_trend_insights(
        report=report,
    )

    evidence = build_trend_evidence(
        report=report,
        insights=insights,
    )

    categories = {
        entry.category
        for entry in evidence
    }

    assert (
        "publishing" in categories
    )

    assert (
        "reviews" in categories
    )

    assert (
        "engagement" not in categories
    )