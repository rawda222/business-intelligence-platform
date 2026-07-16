"""
Trend Insight Service Tests

Verifies deterministic insight generation for representative report
shapes without relying on MongoDB.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.business_trend_report_service import (
    BusinessTrendReport,
)
from app.services.post_trend_service import (
    PostsPerWeekBucket,
    PostsPerWeekTrend,
)
from app.services.review_trend_service import (
    ReviewsPerMonthBucket,
    ReviewsPerMonthTrend,
)
from app.services.trend_foundation_service import (
    BusinessTrendFoundationStats,
)
from app.services.trend_insight_service import (
    build_trend_insights,
)


def _make_report(
    *,
    total_posts: int,
    weekly_counts,
    monthly_ratings,
    monthly_review_counts,
) -> BusinessTrendReport:
    """
    Build a synthetic BusinessTrendReport for insight testing.
    """

    business_id = uuid4()

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

    foundation = BusinessTrendFoundationStats(
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

    reviews_per_month = ReviewsPerMonthTrend(
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

    return BusinessTrendReport(
        business_id=business_id,
        range_start=range_start,
        range_end=range_end,
        review_source="google_maps",
        foundation=foundation,
        posts_per_week=posts_per_week,
        reviews_per_month=reviews_per_month,
        engagement_curves=[],
    )


def test_no_posts_and_no_reviews_produce_warnings():
    """When nothing was published, warnings must be emitted."""

    report = _make_report(
        total_posts=0,
        weekly_counts=[0, 0, 0],
        monthly_ratings=[None, None, None],
        monthly_review_counts=[0, 0, 0],
    )

    insights = build_trend_insights(
        report=report,
    )

    codes = [
        insight.code
        for insight in insights
    ]

    assert "publishing_activity" in codes
    assert "review_volume" in codes

    activity = next(
        insight
        for insight in insights
        if insight.code == "publishing_activity"
    )

    assert activity.severity == "warning"

    volume = next(
        insight
        for insight in insights
        if insight.code == "review_volume"
    )

    assert volume.severity == "warning"


def test_increasing_activity_and_improving_rating():
    """
    Publishing activity increasing and rating improving must produce
    an info trend and an info rating insight.
    """

    report = _make_report(
        total_posts=6,
        weekly_counts=[1, 1, 4],
        monthly_ratings=[3.5, None, 4.5],
        monthly_review_counts=[3, 2, 3],
    )

    insights = build_trend_insights(
        report=report,
    )

    trend = next(
        insight
        for insight in insights
        if insight.code == "publishing_trend"
    )

    assert trend.severity == "info"

    assert (
        "increased"
        in trend.message.lower()
    )

    rating = next(
        insight
        for insight in insights
        if insight.code == "rating_direction"
    )

    assert rating.severity == "info"


def test_decreasing_activity_and_declining_rating():
    """
    Publishing activity decreasing and rating dropping must produce
    warning insights.
    """

    report = _make_report(
        total_posts=9,
        weekly_counts=[
            4,
            3,
            1,
            1,
        ],
        monthly_ratings=[4.5, None, 3.5],
        monthly_review_counts=[3, 2, 1],
    )

    insights = build_trend_insights(
        report=report,
    )

    trend = next(
        insight
        for insight in insights
        if insight.code == "publishing_trend"
    )

    assert trend.severity == "warning"

    assert (
        "decreased"
        in trend.message.lower()
    )

    rating = next(
        insight
        for insight in insights
        if insight.code == "rating_direction"
    )

    assert rating.severity == "warning"


def test_low_review_volume_when_positive():
    """
    Even with positive reviews, low volume must be warned about.
    """

    report = _make_report(
        total_posts=3,
        weekly_counts=[1, 1, 1],
        monthly_ratings=[4.5, None, None],
        monthly_review_counts=[2, 1, 1],
    )

    insights = build_trend_insights(
        report=report,
    )

    volume = next(
        insight
        for insight in insights
        if insight.code == "review_volume"
    )

    assert volume.severity == "warning"

    assert (
        "low"
        in volume.message.lower()
    )