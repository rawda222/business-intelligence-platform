"""
Business Trend Intelligence Service Tests
"""

from datetime import UTC, date, datetime
from uuid import UUID

from app.services.business_trend_intelligence_service import (
    build_business_trend_intelligence,
)
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


_BUSINESS_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

_RANGE_START = datetime(
    2026,
    6,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    9,
    1,
    tzinfo=UTC,
)


def _report(
    posts_by_platform: dict[str, int],
    comments_by_platform: dict[str, int],
    reviews_by_source: dict[str, int],
) -> BusinessTrendReport:
    """Build one deterministic business trend report."""

    total_posts = sum(
        posts_by_platform.values()
    )

    total_comments = sum(
        comments_by_platform.values()
    )

    total_reviews = sum(
        reviews_by_source.values()
    )

    foundation = (
        BusinessTrendFoundationStats(
            business_id=_BUSINESS_ID,
            total_posts=total_posts,
            total_post_metric_snapshots=0,
            total_comments=total_comments,
            total_customer_reviews=(
                total_reviews
            ),
            posts_by_platform=(
                posts_by_platform
            ),
            comments_by_platform=(
                comments_by_platform
            ),
            reviews_by_source=(
                reviews_by_source
            ),
        )
    )

    posts_per_week = PostsPerWeekTrend(
        business_id=_BUSINESS_ID,
        range_start=_RANGE_START,
        range_end=_RANGE_END,
        buckets=[
            PostsPerWeekBucket(
                week_start=date(
                    2026,
                    6,
                    1,
                ),
                post_count=total_posts,
            ),
            PostsPerWeekBucket(
                week_start=date(
                    2026,
                    6,
                    8,
                ),
                post_count=total_posts,
            ),
        ],
        total_posts=total_posts,
    )

    reviews_per_month = (
        ReviewsPerMonthTrend(
            business_id=_BUSINESS_ID,
            source="google_maps",
            range_start=_RANGE_START,
            range_end=_RANGE_END,
            buckets=[
                ReviewsPerMonthBucket(
                    month_start=date(
                        2026,
                        6,
                        1,
                    ),
                    review_count=(
                        total_reviews
                    ),
                    meaningful_review_count=(
                        total_reviews
                    ),
                    rating_average=(
                        4.2
                        if total_reviews > 0
                        else None
                    ),
                ),
            ],
            total_reviews=total_reviews,
            total_meaningful_reviews=(
                total_reviews
            ),
        )
    )

    return BusinessTrendReport(
        business_id=_BUSINESS_ID,
        range_start=_RANGE_START,
        range_end=_RANGE_END,
        review_source="google_maps",
        foundation=foundation,
        posts_per_week=posts_per_week,
        reviews_per_month=(
            reviews_per_month
        ),
        engagement_curves=[],
    )


def test_builds_business_scoped_intelligence():
    """The intelligence should preserve the report scope."""

    report = _report(
        posts_by_platform={
            "facebook": 4,
            "instagram": 6,
        },
        comments_by_platform={
            "facebook": 2,
            "instagram": 3,
        },
        reviews_by_source={
            "google_maps": 8,
        },
    )

    result = (
        build_business_trend_intelligence(
            report
        )
    )

    assert (
        result.business_id
        == _BUSINESS_ID
    )

    assert result.report is report

    assert result.range_start == _RANGE_START

    assert result.range_end == _RANGE_END

    assert result.insights

    assert result.evidence


def test_detects_new_social_sources_since_legacy_swot():
    """
    Facebook and Instagram should be new relative to the old SWOT.
    """

    result = (
        build_business_trend_intelligence(
            _report(
                posts_by_platform={
                    "facebook": 4,
                    "instagram": 6,
                },
                comments_by_platform={
                    "facebook": 2,
                    "instagram": 3,
                },
                reviews_by_source={
                    "google_maps": 8,
                },
            )
        )
    )

    assert (
        result.baseline_sources
        == (
            "business_profile",
            "google_maps_reviews",
        )
    )

    assert (
        result.new_sources_since_baseline
        == (
            "facebook",
            "instagram",
        )
    )


def test_source_coverage_uses_observed_records():
    """Coverage counts should come from report foundation data."""

    result = (
        build_business_trend_intelligence(
            _report(
                posts_by_platform={
                    "facebook": 4,
                    "instagram": 6,
                },
                comments_by_platform={
                    "facebook": 2,
                    "instagram": 3,
                },
                reviews_by_source={
                    "google_maps": 8,
                },
            )
        )
    )

    coverage = {
        entry.source: entry
        for entry in result.source_coverage
    }

    assert coverage[
        "business_profile"
    ].available

    assert coverage[
        "google_maps_reviews"
    ].review_count == 8

    assert coverage[
        "facebook"
    ].post_count == 4

    assert coverage[
        "facebook"
    ].comment_count == 2

    assert coverage[
        "instagram"
    ].post_count == 6

    assert coverage[
        "instagram"
    ].comment_count == 3


def test_missing_social_source_is_not_claimed():
    """An absent Instagram dataset must not be marked available."""

    result = (
        build_business_trend_intelligence(
            _report(
                posts_by_platform={
                    "facebook": 4,
                },
                comments_by_platform={
                    "facebook": 2,
                },
                reviews_by_source={
                    "google_maps": 8,
                },
            )
        )
    )

    coverage = {
        entry.source: entry
        for entry in result.source_coverage
    }

    assert coverage[
        "facebook"
    ].available

    assert not coverage[
        "instagram"
    ].available

    assert (
        result.new_sources_since_baseline
        == (
            "facebook",
        )
    )

    assert any(
        "Instagram" in warning
        for warning in result.warnings
    )


def test_empty_report_exposes_data_quality_warnings():
    """Missing records should produce warnings, not fake evidence."""

    result = (
        build_business_trend_intelligence(
            _report(
                posts_by_platform={},
                comments_by_platform={},
                reviews_by_source={},
            )
        )
    )

    coverage = {
        entry.source: entry
        for entry in result.source_coverage
    }

    assert coverage[
        "business_profile"
    ].available

    assert not coverage[
        "google_maps_reviews"
    ].available

    assert not coverage[
        "facebook"
    ].available

    assert not coverage[
        "instagram"
    ].available

    assert (
        result.new_sources_since_baseline
        == ()
    )

    assert len(
        result.warnings
    ) == 3