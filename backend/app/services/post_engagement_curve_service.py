"""
Post Engagement Curve Service

Provides a per-post engagement curve derived from historical metric
snapshots.

Design decisions:

- The curve is bucketed by UTC calendar date to keep results
  comparable across time zones.
- Each bucket exposes the latest snapshot values captured inside
  the day. This avoids arithmetic assumptions when multiple
  snapshots are recorded on the same date.
- Empty days remain absent from the output because we never
  fabricate data points. Consumers may render sparse curves or fill
  gaps at their own layer if needed.
- All queries strictly scope by business_id, social_account_id,
  and social_post_id so the tenant isolation guarantees stay intact.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from beanie import PydanticObjectId

from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)


# ============================================================
# Errors
# ============================================================
class PostEngagementCurvePostNotFoundError(
    ValueError
):
    """
    Raised when the requested post cannot be resolved inside its
    business and social-account scope.
    """


# ============================================================
# Result Dataclasses
# ============================================================
@dataclass(slots=True)
class PostEngagementCurvePoint:
    """
    One daily engagement observation for a post.

    day:
        UTC calendar date.

    captured_at:
        Timestamp of the latest snapshot inside the day.

    likes:
        Latest known likes count on that day.

    reactions:
        Latest known combined reactions count on that day.

    comments:
        Latest known comments count on that day.

    shares:
        Latest known shares count on that day.

    views:
        Latest known views count on that day.
    """

    day: date

    captured_at: datetime

    likes: int | None

    reactions: int | None

    comments: int | None

    shares: int | None

    views: int | None


@dataclass(slots=True)
class PostEngagementCurve:
    """
    Complete per-post engagement curve.
    """

    business_id: UUID

    social_account_id: UUID

    social_post_id: PydanticObjectId

    range_start: datetime

    range_end: datetime

    points: list[
        PostEngagementCurvePoint
    ]


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
# Curve Query
# ============================================================
async def get_post_engagement_curve(
    *,
    business_id: UUID,
    social_account_id: UUID,
    social_post_id: PydanticObjectId,
    range_start: datetime,
    range_end: datetime,
) -> PostEngagementCurve:
    """
    Return the daily engagement curve for one social post.

    The range is filtered by snapshot captured_at:
    - range_start is inclusive.
    - range_end is exclusive.

    Only the latest snapshot inside each UTC day is used. Days
    without any snapshot remain absent from the output.

    Raises:
        PostEngagementCurvePostNotFoundError:
            The post is not found inside the requested business and
            social-account scope.
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

    scoped_post = await SocialPostDocument.find_one(
        SocialPostDocument.business_id
        == business_id,
        SocialPostDocument.social_account_id
        == social_account_id,
        SocialPostDocument.id
        == social_post_id,
    )

    if scoped_post is None:
        raise PostEngagementCurvePostNotFoundError(
            "Social post not found inside "
            "the requested tenant scope."
        )

    matching_snapshots = (
        PostMetricSnapshotDocument.find(
            PostMetricSnapshotDocument.social_post_id
            == social_post_id,
            PostMetricSnapshotDocument.captured_at
            >= normalized_start,
            PostMetricSnapshotDocument.captured_at
            < normalized_end,
        )
    )

    latest_by_day: dict[
        date,
        PostMetricSnapshotDocument,
    ] = {}

    async for snapshot in matching_snapshots:
        captured_at = _ensure_utc(
            snapshot.captured_at,
        )

        day_key = captured_at.date()

        current_latest = latest_by_day.get(
            day_key,
        )

        if current_latest is None:
            latest_by_day[day_key] = snapshot
            continue

        current_captured_at = _ensure_utc(
            current_latest.captured_at,
        )

        if captured_at > current_captured_at:
            latest_by_day[day_key] = snapshot

    points: list[
        PostEngagementCurvePoint
    ] = []

    for day_key in sorted(
        latest_by_day.keys(),
    ):
        latest_snapshot = latest_by_day[
            day_key
        ]

        metrics = latest_snapshot.metrics

        points.append(
            PostEngagementCurvePoint(
                day=day_key,
                captured_at=_ensure_utc(
                    latest_snapshot.captured_at,
                ),
                likes=metrics.likes,
                reactions=metrics.reactions,
                comments=metrics.comments,
                shares=metrics.shares,
                views=metrics.views,
            )
        )

    return PostEngagementCurve(
        business_id=business_id,
        social_account_id=social_account_id,
        social_post_id=social_post_id,
        range_start=normalized_start,
        range_end=normalized_end,
        points=points,
    )