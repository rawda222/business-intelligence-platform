"""
Business Trend Report Service

Aggregates every trend surface currently available for one business
into a single in-memory report.

Sources:

- Trend foundation statistics.
- Posts per week trend.
- Reviews per month trend.
- Engagement curves for posts published inside the range.

Reports are Business-scoped. Every query filters by business_id.
Reports are not persisted at this stage.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    CustomerVoiceSource,
)
from app.services.post_engagement_curve_service import (
    PostEngagementCurve,
    PostEngagementCurvePostNotFoundError,
    get_post_engagement_curve,
)
from app.services.post_trend_service import (
    PostsPerWeekTrend,
    get_posts_per_week_trend,
)
from app.services.review_trend_service import (
    ReviewsPerMonthTrend,
    get_reviews_per_month_trend,
)
from app.services.trend_foundation_service import (
    BusinessTrendFoundationStats,
    get_business_trend_foundation_stats,
)


# ============================================================
# Report Result
# ============================================================
@dataclass(slots=True)
class BusinessTrendReport:
    """
    Aggregated trend report for one business.
    """

    business_id: UUID

    range_start: datetime

    range_end: datetime

    review_source: CustomerVoiceSource

    foundation: BusinessTrendFoundationStats

    posts_per_week: PostsPerWeekTrend

    reviews_per_month: ReviewsPerMonthTrend

    engagement_curves: list[
        PostEngagementCurve
    ] = field(
        default_factory=list,
    )


# ============================================================
# Range Normalization
# ============================================================
def _ensure_utc(
    value: datetime,
) -> datetime:
    """Return a UTC-aware datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )


# ============================================================
# Engagement Curves Loader
# ============================================================
async def _load_engagement_curves_for_posts_in_range(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
    max_posts: int,
) -> list[
    PostEngagementCurve
]:
    """
    Load per-post engagement curves for posts published inside the
    report range.

    max_posts caps the number of posts to keep the report bounded.
    """

    if max_posts <= 0:
        return []

    posts_query = SocialPostDocument.find(
        SocialPostDocument.business_id
        == business_id,
        SocialPostDocument.published_at
        >= range_start,
        SocialPostDocument.published_at
        < range_end,
    ).sort(
        -SocialPostDocument.published_at,
    ).limit(
        max_posts,
    )

    curves: list[
        PostEngagementCurve
    ] = []

    async for post in posts_query:
        try:
            curve = (
                await get_post_engagement_curve(
                    business_id=business_id,
                    social_account_id=(
                        post.social_account_id
                    ),
                    social_post_id=post.id,
                    range_start=range_start,
                    range_end=range_end,
                )
            )
        except PostEngagementCurvePostNotFoundError:
            continue

        curves.append(curve)

    return curves


# ============================================================
# Report Builder
# ============================================================
async def build_business_trend_report(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
    review_source: CustomerVoiceSource = (
        "google_maps"
    ),
    max_engagement_curves: int = 5,
) -> BusinessTrendReport:
    """
    Build the aggregated trend report for one business.
    """

    if range_end <= range_start:
        raise ValueError(
            "range_end must be strictly "
            "greater than range_start."
        )

    normalized_start = _ensure_utc(
        range_start,
    )

    normalized_end = _ensure_utc(
        range_end,
    )

    foundation = await (
        get_business_trend_foundation_stats(
            business_id,
        )
    )

    posts_per_week = await (
        get_posts_per_week_trend(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
        )
    )

    reviews_per_month = await (
        get_reviews_per_month_trend(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
            source=review_source,
        )
    )

    engagement_curves = await (
        _load_engagement_curves_for_posts_in_range(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
            max_posts=max_engagement_curves,
        )
    )

    return BusinessTrendReport(
        business_id=business_id,
        range_start=normalized_start,
        range_end=normalized_end,
        review_source=review_source,
        foundation=foundation,
        posts_per_week=posts_per_week,
        reviews_per_month=reviews_per_month,
        engagement_curves=engagement_curves,
    )