"""
Normalized Social Storage Service

Bridges platform-independent normalized social data with MongoDB
social-post persistence and historical metric snapshots.

The service keeps platform-specific metric meaning intact:

- Instagram likes remain likes.
- Facebook combined reactions remain reactions.
- Missing metrics remain None.
- Observed zero values remain zero.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)
from app.schemas.normalized_social import (
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)

from app.services.post_metric_service import (
    MetricSnapshotResult,
    ensure_utc,
)
from app.services.post_metric_service import (
    MetricSnapshotResult,
    ensure_utc,
    record_metric_snapshot,
)

# ============================================================
# Storage Result
# ============================================================
@dataclass(slots=True)
class NormalizedSocialPostStorageResult:
    """
    Result returned after storing one normalized social post.

    post:
        The persisted social-post document.

    snapshot:
        The result of recording the normalized metric observation.

    post_created:
        True when the social post did not previously exist.

    post_updated:
        True when an existing social post's content was updated.
    """

    post: SocialPostDocument

    snapshot: MetricSnapshotResult

    post_created: bool

    post_updated: bool


# ============================================================
# Metrics Mapping
# ============================================================
def map_normalized_metrics(
    metrics: NormalizedSocialMetrics,
) -> SocialPostMetrics:
    """
    Convert normalized connector metrics into MongoDB metrics.

    Metric semantics are preserved:

    - likes are not copied into reactions.
    - reactions are not copied into likes.
    - zero remains an observed zero.
    - missing values remain None.
    - captured_at is normalized to UTC.
    """

    return SocialPostMetrics(
        likes=metrics.likes,
        reactions=metrics.reactions,
        comments=metrics.comments,
        shares=metrics.shares,
        saves=metrics.saves,
        views=metrics.views,
        reach=metrics.reach,
        impressions=metrics.impressions,
        captured_at=ensure_utc(
            metrics.captured_at,
        ),
    )
# ============================================================
# Existing Post Lookup
# ============================================================
async def find_existing_normalized_post(
    normalized_post: NormalizedSocialPost,
) -> SocialPostDocument | None:
    """
    Find an existing social post inside the supplied tenant scope.

    A platform_post_id is not assumed to be globally unique.

    The complete lookup scope is:

    - business_id
    - social_account_id
    - platform
    - platform_post_id

    This prevents one business or social account from matching a
    post owned by another tenant or account.
    """

    return await SocialPostDocument.find_one(
        SocialPostDocument.business_id
        == normalized_post.business_id,
        SocialPostDocument.social_account_id
        == normalized_post.social_account_id,
        SocialPostDocument.platform
        == normalized_post.platform,
        SocialPostDocument.platform_post_id
        == normalized_post.platform_post_id,
    )

# ============================================================
# Raw Data Mapping
# ============================================================
def build_social_post_raw_data(
    normalized_post: NormalizedSocialPost,
) -> dict[str, Any]:
    """
    Build the minimized raw payload stored with a social post.

    The normalizer already minimizes platform payloads. This helper
    preserves that normalized traceability data and adds fields that
    currently have no dedicated SocialPostDocument column.
    """

    raw_data = dict(
        normalized_post.raw_data
    )

    if normalized_post.tagged_accounts:
        raw_data["tagged_accounts"] = list(
            normalized_post.tagged_accounts
        )

    if normalized_post.location_name is not None:
        raw_data["location_name"] = (
            normalized_post.location_name
        )

    if normalized_post.is_pinned is not None:
        raw_data["is_pinned"] = (
            normalized_post.is_pinned
        )

    return raw_data

# ============================================================
# Post Creation
# ============================================================
async def create_normalized_social_post(
    normalized_post: NormalizedSocialPost,
) -> SocialPostDocument:
    """
    Create a MongoDB social-post document from normalized data.

    latest_metrics is intentionally not populated here.

    Metric persistence is owned by record_metric_snapshot(), which
    creates the historical snapshot and synchronizes latest_metrics
    through one consistent service path.
    """

    now = datetime.now(
        UTC,
    )

    captured_at = ensure_utc(
        normalized_post.metrics.captured_at
    )

    post = SocialPostDocument(
        business_id=normalized_post.business_id,
        social_account_id=(
            normalized_post.social_account_id
        ),
        platform=normalized_post.platform,
        platform_post_id=(
            normalized_post.platform_post_id
        ),
        published_at=normalized_post.published_at,
        post_url=normalized_post.post_url,
        content_type=normalized_post.content_type,
        text=normalized_post.text,
        hashtags=list(
            normalized_post.hashtags
        ),
        mentions=list(
            normalized_post.mentions
        ),
        media_urls=list(
            normalized_post.media_urls
        ),
        language=normalized_post.language,
        connector_type=(
            normalized_post.connector_type
        ),
        raw_data=build_social_post_raw_data(
            normalized_post
        ),
        collected_at=captured_at,
        created_at=now,
        updated_at=now,
    )

    await post.insert()

    return post

# ============================================================
# Post Content Update
# ============================================================
async def update_normalized_social_post_content(
    *,
    post: SocialPostDocument,
    normalized_post: NormalizedSocialPost,
) -> bool:
    """
    Safely update an existing social post from normalized data.

    Update policy:

    - A non-None scalar replaces the stored value.
    - A None scalar preserves the stored value.
    - A non-empty list replaces the stored list.
    - An empty list preserves the stored list.
    - raw_data values are merged without deleting existing keys.
    - collected_at advances only when the incoming collection time
      is newer.
    - latest_metrics is not modified here. Metric persistence remains
      the responsibility of record_metric_snapshot().

    Returns:
        True when at least one stored content field changed.
        False when the incoming normalized content caused no change.
    """

    changed = False

    # ========================================================
    # Optional Scalar Fields
    # ========================================================
    scalar_updates = {
        "published_at": normalized_post.published_at,
        "post_url": normalized_post.post_url,
        "content_type": normalized_post.content_type,
        "text": normalized_post.text,
        "language": normalized_post.language,
        "connector_type": normalized_post.connector_type,
    }

    for field_name, incoming_value in scalar_updates.items():
        if incoming_value is None:
            continue

        current_value = getattr(
            post,
            field_name,
        )

        if current_value != incoming_value:
            setattr(
                post,
                field_name,
                incoming_value,
            )

            changed = True

    # ========================================================
    # Ordered List Fields
    # ========================================================
    list_updates = {
        "hashtags": normalized_post.hashtags,
        "mentions": normalized_post.mentions,
        "media_urls": normalized_post.media_urls,
    }

    for field_name, incoming_values in list_updates.items():
        if not incoming_values:
            continue

        normalized_values = list(
            incoming_values
        )

        current_values = list(
            getattr(
                post,
                field_name,
            )
            or []
        )

        if current_values != normalized_values:
            setattr(
                post,
                field_name,
                normalized_values,
            )

            changed = True

    # ========================================================
    # Minimized Raw Data Merge
    # ========================================================
    incoming_raw_data = build_social_post_raw_data(
        normalized_post
    )

    merged_raw_data = dict(
        post.raw_data
        or {}
    )

    for key, value in incoming_raw_data.items():
        if value is None:
            continue

        merged_raw_data[key] = value

    if merged_raw_data != (
        post.raw_data
        or {}
    ):
        post.raw_data = merged_raw_data
        changed = True

    # ========================================================
    # Collection Timestamp
    # ========================================================
    incoming_collected_at = ensure_utc(
        normalized_post.metrics.captured_at
    )

    current_collected_at = (
        ensure_utc(post.collected_at)
        if post.collected_at is not None
        else None
    )

    if (
        current_collected_at is None
        or incoming_collected_at
        > current_collected_at
    ):
        post.collected_at = incoming_collected_at
        changed = True

    # ========================================================
    # Persist Only When Needed
    # ========================================================
    if not changed:
        return False

    post.updated_at = datetime.now(
        UTC,
    )

    await post.save()

    return True
# ============================================================
# Complete Normalized Post Storage
# ============================================================
async def store_normalized_social_post(
    normalized_post: NormalizedSocialPost,
    *,
    collection_run_id: UUID | None = None,
) -> NormalizedSocialPostStorageResult:
    """
    Store one normalized social post and its metric observation.

    Workflow:
    - Find the post inside the exact tenant scope.
    - Create it when it does not exist.
    - Safely update its content when it already exists.
    - Map and record its historical metric observation.
    - Reload and return the persisted post.
    """

    existing_post = await find_existing_normalized_post(
        normalized_post
    )

    post_created = False
    post_updated = False

    if existing_post is None:
        post = await create_normalized_social_post(
            normalized_post
        )

        post_created = True
    else:
        post = existing_post

        post_updated = (
            await update_normalized_social_post_content(
                post=post,
                normalized_post=normalized_post,
            )
        )

    stored_metrics = map_normalized_metrics(
        normalized_post.metrics
    )

    snapshot_result = await record_metric_snapshot(
        business_id=normalized_post.business_id,
        social_account_id=(
            normalized_post.social_account_id
        ),
        social_post_id=post.id,
        metrics=stored_metrics,
        captured_at=(
            normalized_post.metrics.captured_at
        ),
        connector_type=(
            normalized_post.connector_type
        ),
        collection_run_id=collection_run_id,
    )

    refreshed_post = await SocialPostDocument.get(
        post.id
    )

    if refreshed_post is None:
        raise RuntimeError(
            "Stored social post could not be reloaded "
            "after metric persistence."
        )

    return NormalizedSocialPostStorageResult(
        post=refreshed_post,
        snapshot=snapshot_result,
        post_created=post_created,
        post_updated=post_updated,
    )
