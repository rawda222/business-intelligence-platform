"""
Social Post Document Model

Stores normalized social-media posts collected from different
platforms.

The document keeps:
- A normalized cross-platform representation.
- The latest known engagement metrics.
- The original connector payload for traceability.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel


# ============================================================
# Embedded Metrics Model
# ============================================================
class SocialPostMetrics(BaseModel):
    """
    Latest known metrics for a social-media post.

    Metrics are optional because platforms expose different fields.
    A missing metric is represented by None, not zero.
    """

    likes: int | None = Field(
        default=None,
        ge=0,
    )

    reactions: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Total combined reactions reported by platforms "
            "such as Facebook."
        ),
    )

    comments: int | None = Field(
        default=None,
        ge=0,
    )

    shares: int | None = Field(
        default=None,
        ge=0,
    )

    saves: int | None = Field(
        default=None,
        ge=0,
    )

    views: int | None = Field(
        default=None,
        ge=0,
    )

    reach: int | None = Field(
        default=None,
        ge=0,
    )

    impressions: int | None = Field(
        default=None,
        ge=0,
    )

    captured_at: datetime | None = None


# ============================================================
# Social Post Document
# ============================================================
class SocialPostDocument(Document):
    """
    Normalized social-media post stored in MongoDB.

    Every document is scoped by:
    - business_id
    - social_account_id

    Platform-specific fields that are not part of the common model
    remain available inside raw_data.
    """

    # ========================================================
    # Tenant and Account Identity
    # ========================================================
    business_id: UUID

    social_account_id: UUID

    # ========================================================
    # Platform Post Identity
    # ========================================================
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
    # Publishing Information
    # ========================================================
    published_at: datetime | None = None

    post_url: str | None = Field(
        default=None,
        max_length=2000,
    )

    content_type: str | None = Field(
        default=None,
        max_length=100,
    )

    # ========================================================
    # Normalized Content
    # ========================================================
    text: str | None = None

    hashtags: list[str] = Field(
        default_factory=list,
    )

    mentions: list[str] = Field(
        default_factory=list,
    )

    media_urls: list[str] = Field(
        default_factory=list,
    )

    language: str | None = Field(
        default=None,
        max_length=20,
    )

    # ========================================================
    # Latest Known Metrics
    # ========================================================
    latest_metrics: SocialPostMetrics = Field(
        default_factory=SocialPostMetrics,
    )

    # ========================================================
    # Source and Raw Data
    # ========================================================
    connector_type: str = Field(
        default="apify",
        min_length=1,
        max_length=50,
    )

    raw_data: dict[str, Any] = Field(
        default_factory=dict,
    )

    # ========================================================
    # Collection Metadata
    # ========================================================
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ========================================================
    # Beanie Settings and MongoDB Indexes
    # ========================================================
    class Settings:
        name = "social_posts"

        indexes = [
            IndexModel(
                [
                    ("platform", ASCENDING),
                    ("social_account_id", ASCENDING),
                    ("platform_post_id", ASCENDING),
                ],
                name="uq_social_posts_platform_account_post",
                unique=True,
            ),
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("published_at", DESCENDING),
                ],
                name="ix_social_posts_business_published_at",
            ),
            IndexModel(
                [
                    ("social_account_id", ASCENDING),
                    ("published_at", DESCENDING),
                ],
                name="ix_social_posts_account_published_at",
            ),
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("platform", ASCENDING),
                    ("published_at", DESCENDING),
                ],
                name="ix_social_posts_business_platform_published_at",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<SocialPost "
            f"{self.platform}:{self.platform_post_id} "
            f"business={self.business_id}>"
        )