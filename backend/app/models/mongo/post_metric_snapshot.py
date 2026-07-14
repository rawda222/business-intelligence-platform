"""
Post Metric Snapshot Document Model

Stores historical engagement-metric snapshots for social-media posts.

Unlike SocialPostDocument.latest_metrics, snapshots preserve how
metrics change over time and provide the historical foundation for:

- Engagement velocity
- Views growth
- Comment growth
- Post momentum
- Time-to-peak analysis
- Performance by post age
"""

from datetime import UTC, datetime
from uuid import UUID

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.mongo.social_post import SocialPostMetrics


class PostMetricSnapshotDocument(Document):
    """
    Historical metric observation for one social-media post.

    Every snapshot is scoped by:

    - business_id
    - social_account_id
    - social_post_id
    - platform_post_id

    The snapshot preserves the metrics observed at captured_at.
    """

    # ========================================================
    # Tenant and Account Identity
    # ========================================================
    business_id: UUID

    social_account_id: UUID

    # ========================================================
    # Social Post Identity
    # ========================================================
    social_post_id: PydanticObjectId

    platform: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    platform_post_id: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    # ========================================================
    # Historical Metrics
    # ========================================================
    metrics: SocialPostMetrics = Field(
        default_factory=SocialPostMetrics,
    )

    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ========================================================
    # Post-Age Context
    # ========================================================
    post_age_seconds: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Number of seconds between post publication "
            "and this metric observation."
        ),
    )

    # ========================================================
    # Collection Metadata
    # ========================================================
    connector_type: str = Field(
        default="apify",
        min_length=1,
        max_length=50,
    )

    collection_run_id: UUID | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ========================================================
    # Beanie Settings and MongoDB Indexes
    # ========================================================
    class Settings:
        name = "post_metric_snapshots"

        indexes = [
            IndexModel(
                [
                    ("social_post_id", ASCENDING),
                    ("captured_at", ASCENDING),
                ],
                name="uq_metric_snapshots_post_captured_at",
                unique=True,
            ),
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("captured_at", DESCENDING),
                ],
                name="ix_metric_snapshots_business_captured_at",
            ),
            IndexModel(
                [
                    ("social_account_id", ASCENDING),
                    ("captured_at", DESCENDING),
                ],
                name="ix_metric_snapshots_account_captured_at",
            ),
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("platform", ASCENDING),
                    ("captured_at", DESCENDING),
                ],
                name=(
                    "ix_metric_snapshots_"
                    "business_platform_captured_at"
                ),
            ),
            IndexModel(
                [
                    ("social_post_id", ASCENDING),
                    ("post_age_seconds", ASCENDING),
                ],
                name="ix_metric_snapshots_post_age",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<PostMetricSnapshot "
            f"post={self.social_post_id} "
            f"captured_at={self.captured_at}>"
        )