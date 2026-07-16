"""
Trend Foundation Service

Provides tenant-scoped foundational statistics used by the trend
analysis layer.

Current statistics:

- Total posts persisted.
- Total post-metric snapshots persisted.
- Total comments persisted.
- Total customer reviews persisted.
- Posts by platform.
- Comments by platform.
- Reviews by customer-voice source.

These stats intentionally avoid business logic such as sentiment,
velocity, or momentum. They provide the raw denominators required
by the higher trend analysis stages.
"""

from dataclasses import dataclass
from uuid import UUID

from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)


# ============================================================
# Trend Foundation Stats Result
# ============================================================
@dataclass(slots=True)
class BusinessTrendFoundationStats:
    """
    Foundational trend statistics for one business.

    All fields are strictly non-negative integer counts.
    """

    business_id: UUID

    total_posts: int

    total_post_metric_snapshots: int

    total_comments: int

    total_customer_reviews: int

    posts_by_platform: dict[str, int]

    comments_by_platform: dict[str, int]

    reviews_by_source: dict[str, int]


# ============================================================
# Aggregation Helpers
# ============================================================
# ============================================================
# Aggregation Helper
# ============================================================
async def _group_counts(
    document_cls,
    *,
    business_id: UUID,
    group_field: str,
) -> dict[str, int]:
    """
    Return grouped counts filtered by business_id.

    Uses MongoDB aggregation without loading documents into Python
    memory.

    The business_id filter is applied via find(), then $group is
    performed inside the aggregation. This avoids passing a raw
    Python UUID directly into the Motor aggregation pipeline, which
    Motor rejects unless the client uses a fixed UuidRepresentation.
    """

    pipeline = [
        {
            "$group": {
                "_id": (
                    f"${group_field}"
                ),
                "count": {
                    "$sum": 1,
                },
            },
        },
    ]

    documents = document_cls.find(
        document_cls.business_id
        == business_id,
    )

    grouped_counts: dict[str, int] = {}

    async for entry in (
        documents.aggregate(pipeline)
    ):
        key = entry.get("_id")

        if not isinstance(key, str):
            continue

        grouped_counts[key] = int(
            entry.get("count", 0),
        )

    return grouped_counts


# ============================================================
# Foundation Stats Service
# ============================================================
async def get_business_trend_foundation_stats(
    business_id: UUID,
) -> BusinessTrendFoundationStats:
    """
    Compute foundational trend statistics for one business.

    All queries strictly filter by business_id to preserve tenant
    isolation.
    """

    total_posts = await (
        SocialPostDocument.find(
            SocialPostDocument.business_id
            == business_id,
        ).count()
    )

    total_post_metric_snapshots = await (
        PostMetricSnapshotDocument.find(
            PostMetricSnapshotDocument.business_id
            == business_id,
        ).count()
    )

    total_comments = await (
        SocialCommentDocument.find(
            SocialCommentDocument.business_id
            == business_id,
        ).count()
    )

    total_customer_reviews = await (
        CustomerReviewDocument.find(
            CustomerReviewDocument.business_id
            == business_id,
        ).count()
    )

    posts_by_platform = await _group_counts(
        SocialPostDocument,
        business_id=business_id,
        group_field="platform",
    )

    comments_by_platform = await _group_counts(
        SocialCommentDocument,
        business_id=business_id,
        group_field="platform",
    )

    reviews_by_source = await _group_counts(
        CustomerReviewDocument,
        business_id=business_id,
        group_field="source",
    )

    return BusinessTrendFoundationStats(
        business_id=business_id,
        total_posts=total_posts,
        total_post_metric_snapshots=(
            total_post_metric_snapshots
        ),
        total_comments=total_comments,
        total_customer_reviews=(
            total_customer_reviews
        ),
        posts_by_platform=posts_by_platform,
        comments_by_platform=(
            comments_by_platform
        ),
        reviews_by_source=reviews_by_source,
    )