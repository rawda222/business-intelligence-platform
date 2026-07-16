"""
Post Trend Service

Provides tenant-scoped time-series trends for stored social posts.

Current trends:

- Posts per week bucketed by published_at, normalized to UTC.

Trends deliberately filter by published_at rather than collected_at
because the analytical goal is to understand publishing behavior
over time, not the collector schedule.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.models.mongo.social_post import (
    SocialPostDocument,
)


# ============================================================
# Trend Result
# ============================================================
@dataclass(slots=True)
class PostsPerWeekBucket:
    """
    One weekly bucket in the posts-per-week trend.

    week_start:
        ISO date of the Monday that begins the UTC week.

    post_count:
        Number of posts published inside the week.
    """

    week_start: date

    post_count: int


@dataclass(slots=True)
class PostsPerWeekTrend:
    """
    Complete posts-per-week trend for one business.

    business_id:
        Business owning the trend.

    range_start:
        UTC lower bound applied to published_at, inclusive.

    range_end:
        UTC upper bound applied to published_at, exclusive.

    buckets:
        Ordered weekly buckets covering the full range with zero
        counts filled in for empty weeks.

    total_posts:
        Sum of all bucket counts.
    """

    business_id: UUID

    range_start: datetime

    range_end: datetime

    buckets: list[
        PostsPerWeekBucket
    ]

    total_posts: int


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


def _iso_week_start(
    value: datetime,
) -> date:
    """
    Return the Monday date of the ISO week for a UTC datetime.
    """

    utc_value = _ensure_utc(
        value,
    )

    utc_date = utc_value.date()

    weekday_index = utc_date.weekday()

    return utc_date - timedelta(
        days=weekday_index,
    )


from datetime import datetime, date, timedelta

def _week_starts_within_range(
    range_start: datetime,
    range_end: datetime,
) -> list[date]:  # تم تصحيح الـ Type Hint وإضافة ":" هنا
    """
    Return ordered Monday dates covering the requested range.
    """

    first_week = _iso_week_start(
        range_start,
    )

    last_week = _iso_week_start(
        range_end
        - timedelta(microseconds=1),
    )

    weeks: list[date] = []

    current = first_week

    while current <= last_week:
        weeks.append(current)

        current = current + timedelta(
            days=7,
        )

    return weeks


# ============================================================
# Posts Per Week Query
# ============================================================
async def get_posts_per_week_trend(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> PostsPerWeekTrend:
    """
    Return the posts-per-week trend for one business.

    The range is filtered by published_at:
    - range_start is inclusive.
    - range_end is exclusive.

    Naive datetimes are interpreted as UTC.

    Empty weeks inside the range are represented with post_count=0
    so downstream chart layers can render a continuous timeline.
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

    matching_posts = SocialPostDocument.find(
        SocialPostDocument.business_id
        == business_id,
        SocialPostDocument.published_at
        >= normalized_start,
        SocialPostDocument.published_at
        < normalized_end,
    )

    weekly_counts: dict[date, int] = {}

    total_posts = 0

    async for post in matching_posts:
        published_at = post.published_at

        if published_at is None:
            continue

        week_start = _iso_week_start(
            published_at,
        )

        weekly_counts[week_start] = (
            weekly_counts.get(
                week_start,
                0,
            )
            + 1
        )

        total_posts += 1

    ordered_weeks = _week_starts_within_range(
        normalized_start,
        normalized_end,
    )

    buckets = [
        PostsPerWeekBucket(
            week_start=week_start,
            post_count=weekly_counts.get(
                week_start,
                0,
            ),
        )
        for week_start in ordered_weeks
    ]

    return PostsPerWeekTrend(
        business_id=business_id,
        range_start=normalized_start,
        range_end=normalized_end,
        buckets=buckets,
        total_posts=total_posts,
    )