"""
Post Metric Service

Coordinates historical metric snapshots with the latest metrics
stored on SocialPostDocument.

Responsibilities:

- Preserve tenant and social-account isolation.
- Normalize observation timestamps to UTC.
- Calculate post age at the time of observation.
- Skip rapidly repeated identical observations.
- Preserve later identical observations as evidence of stability.
- Update SocialPostDocument.latest_metrics.
- Handle repeated captured_at values idempotently.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)


# ============================================================
# Configuration
# ============================================================
DEFAULT_IDENTICAL_SNAPSHOT_INTERVAL = timedelta(
    minutes=15,
)


# ============================================================
# Service Result
# ============================================================
@dataclass(slots=True)
class MetricSnapshotResult:
    """
    Result returned after recording a metric observation.

    created:
        True when a new historical snapshot was inserted.

    skipped:
        True when no new snapshot was needed.

    updated_existing:
        True when an existing snapshot at the same captured_at
        timestamp was updated idempotently.
    """

    snapshot: PostMetricSnapshotDocument

    created: bool

    skipped: bool

    updated_existing: bool

    reason: str


# ============================================================
# Service Exceptions
# ============================================================
class SocialPostNotFoundError(Exception):
    """Raised when the requested social post does not exist."""


class SocialPostScopeMismatchError(Exception):
    """
    Raised when a post does not belong to the supplied business
    or social account.
    """


class InvalidMetricTimestampError(Exception):
    """
    Raised when captured_at occurs before the post publication
    timestamp.
    """


# ============================================================
# Date-Time Helpers
# ============================================================
def ensure_utc(value: datetime) -> datetime:
    """
    Return a timezone-aware UTC datetime.

    MongoDB or older application records may contain naive datetime
    values. Naive values are interpreted as UTC for compatibility
    with the existing project data.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


# ============================================================
# Metrics Comparison
# ============================================================
def metric_values(
    metrics: SocialPostMetrics,
) -> tuple[int | None, ...]:
    """
    Return comparable metric values.

    captured_at is intentionally excluded because two observations
    can contain identical metric values at different times.
    """

    return (
        metrics.likes,
        metrics.reactions,
        metrics.comments,
        metrics.shares,
        metrics.saves,
        metrics.views,
        metrics.reach,
        metrics.impressions,
    )


def metrics_are_equal(
    first: SocialPostMetrics,
    second: SocialPostMetrics,
) -> bool:
    """Compare only engagement values, excluding timestamps."""

    return metric_values(first) == metric_values(second)


# ============================================================
# Social Post Lookup
# ============================================================
async def get_scoped_social_post(
    *,
    business_id: UUID,
    social_account_id: UUID,
    social_post_id,
) -> SocialPostDocument:
    """
    Retrieve one post using tenant and account scope.

    MongoDB has no foreign-key enforcement, so every service query
    must include business_id and social_account_id explicitly.
    """

    post = await SocialPostDocument.find_one(
        SocialPostDocument.id == social_post_id,
        SocialPostDocument.business_id == business_id,
        SocialPostDocument.social_account_id
        == social_account_id,
    )

    if post is None:
        existing_post = await SocialPostDocument.get(
            social_post_id
        )

        if existing_post is None:
            raise SocialPostNotFoundError(
                "Social post not found."
            )

        raise SocialPostScopeMismatchError(
            "Social post does not belong to the supplied "
            "business and social account."
        )

    return post


# ============================================================
# Snapshot Queries
# ============================================================
async def get_latest_metric_snapshot(
    social_post_id,
) -> PostMetricSnapshotDocument | None:
    """Return the most recent metric snapshot for one post."""

    snapshots = await PostMetricSnapshotDocument.find(
        PostMetricSnapshotDocument.social_post_id
        == social_post_id
    ).sort(
        -PostMetricSnapshotDocument.captured_at
    ).limit(1).to_list()

    if not snapshots:
        return None

    return snapshots[0]


async def get_snapshot_at_time(
    *,
    social_post_id,
    captured_at: datetime,
) -> PostMetricSnapshotDocument | None:
    """Return a snapshot recorded at an exact observation time."""

    return await PostMetricSnapshotDocument.find_one(
        PostMetricSnapshotDocument.social_post_id
        == social_post_id,
        PostMetricSnapshotDocument.captured_at
        == captured_at,
    )


# ============================================================
# Post-Age Calculation
# ============================================================
def calculate_post_age_seconds(
    *,
    published_at: datetime | None,
    captured_at: datetime,
) -> int | None:
    """
    Calculate post age when publication time is available.

    A snapshot earlier than publication time is rejected.
    """

    if published_at is None:
        return None

    normalized_published_at = ensure_utc(
        published_at
    )

    age_seconds = int(
        (
            captured_at
            - normalized_published_at
        ).total_seconds()
    )

    if age_seconds < 0:
        raise InvalidMetricTimestampError(
            "Metric capture time cannot be earlier "
            "than the post publication time."
        )

    return age_seconds


# ============================================================
# Latest Metrics Update
# ============================================================
async def update_post_latest_metrics(
    *,
    post: SocialPostDocument,
    metrics: SocialPostMetrics,
    captured_at: datetime,
) -> bool:
    """
    Update the latest metrics embedded in the social post.

    Historical or out-of-order observations are allowed to create
    snapshots, but they must not replace a newer latest_metrics value.

    Returns:
        True when latest_metrics was updated.
        False when the observation was older than the current latest.
    """

    current_captured_at = (
        post.latest_metrics.captured_at
        if post.latest_metrics is not None
        else None
    )

    if current_captured_at is not None:
        normalized_current_captured_at = ensure_utc(
            current_captured_at
        )

        if captured_at < normalized_current_captured_at:
            return False

    post.latest_metrics = SocialPostMetrics(
        likes=metrics.likes,
        reactions=metrics.reactions,
        comments=metrics.comments,
        shares=metrics.shares,
        saves=metrics.saves,
        views=metrics.views,
        reach=metrics.reach,
        impressions=metrics.impressions,
        captured_at=captured_at,
    )

    post.updated_at = datetime.now(UTC)

    await post.save()

    return True

# ============================================================
# Record Metric Snapshot
# ============================================================
async def record_metric_snapshot(
    *,
    business_id: UUID,
    social_account_id: UUID,
    social_post_id,
    metrics: SocialPostMetrics,
    captured_at: datetime | None = None,
    connector_type: str = "apify",
    collection_run_id: UUID | None = None,
    identical_snapshot_interval: timedelta = (
        DEFAULT_IDENTICAL_SNAPSHOT_INTERVAL
    ),
) -> MetricSnapshotResult:
    """
    Record a historical metric observation for one social post.

    Rules:

    1. The post must belong to business_id and social_account_id.
    2. captured_at is normalized to UTC.
    3. A timestamp before published_at is rejected.
    4. An existing snapshot at the same timestamp is updated.
    5. Rapid identical observations are skipped.
    6. Identical observations after the minimum interval are stored.
    7. Changed metrics are always stored.
    8. SocialPost.latest_metrics is updated for every valid
       observation, including skipped historical snapshots.
    """

    post = await get_scoped_social_post(
        business_id=business_id,
        social_account_id=social_account_id,
        social_post_id=social_post_id,
    )

    normalized_captured_at = ensure_utc(
        captured_at or datetime.now(UTC)
    )

    post_age_seconds = calculate_post_age_seconds(
        published_at=post.published_at,
        captured_at=normalized_captured_at,
    )

    # ========================================================
    # Idempotent Exact-Timestamp Handling
    # ========================================================
    existing_at_time = await get_snapshot_at_time(
        social_post_id=post.id,
        captured_at=normalized_captured_at,
    )

    if existing_at_time is not None:
        existing_at_time.metrics = SocialPostMetrics(
            likes=metrics.likes,
            reactions=metrics.reactions,
            comments=metrics.comments,
            shares=metrics.shares,
            saves=metrics.saves,
            views=metrics.views,
            reach=metrics.reach,
            impressions=metrics.impressions,
            captured_at=normalized_captured_at,
        )

        existing_at_time.post_age_seconds = (
            post_age_seconds
        )

        existing_at_time.connector_type = (
            connector_type.strip().lower()
        )

        existing_at_time.collection_run_id = (
            collection_run_id
        )

        await existing_at_time.save()

        await update_post_latest_metrics(
            post=post,
            metrics=metrics,
            captured_at=normalized_captured_at,
        )

        return MetricSnapshotResult(
            snapshot=existing_at_time,
            created=False,
            skipped=False,
            updated_existing=True,
            reason="same_timestamp_updated",
        )

    # ========================================================
    # Rapid Identical Observation Handling
    # ========================================================
    latest_snapshot = await get_latest_metric_snapshot(
        post.id
    )

    if latest_snapshot is not None:
        latest_captured_at = ensure_utc(
            latest_snapshot.captured_at
        )

        elapsed = (
            normalized_captured_at
            - latest_captured_at
        )

        if (
            elapsed >= timedelta(0)
            and elapsed < identical_snapshot_interval
            and metrics_are_equal(
                latest_snapshot.metrics,
                metrics,
            )
        ):
            await update_post_latest_metrics(
                post=post,
                metrics=metrics,
                captured_at=normalized_captured_at,
            )

            return MetricSnapshotResult(
                snapshot=latest_snapshot,
                created=False,
                skipped=True,
                updated_existing=False,
                reason="rapid_identical_metrics",
            )

    # ========================================================
    # Create Historical Snapshot
    # ========================================================
    snapshot = PostMetricSnapshotDocument(
        business_id=post.business_id,
        social_account_id=post.social_account_id,
        social_post_id=post.id,
        platform=post.platform,
        platform_post_id=post.platform_post_id,
        metrics=SocialPostMetrics(
            likes=metrics.likes,
            reactions=metrics.reactions,
            comments=metrics.comments,
            shares=metrics.shares,
            saves=metrics.saves,
            views=metrics.views,
            reach=metrics.reach,
            impressions=metrics.impressions,
            captured_at=normalized_captured_at,
        ),
        captured_at=normalized_captured_at,
        post_age_seconds=post_age_seconds,
        connector_type=(
            connector_type.strip().lower()
        ),
        collection_run_id=collection_run_id,
    )

    await snapshot.insert()

    await update_post_latest_metrics(
        post=post,
        metrics=metrics,
        captured_at=normalized_captured_at,
    )

    return MetricSnapshotResult(
        snapshot=snapshot,
        created=True,
        skipped=False,
        updated_existing=False,
        reason="snapshot_created",
    )