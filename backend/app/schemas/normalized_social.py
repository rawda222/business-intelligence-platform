"""
Normalized Social and Customer-Voice Schemas

Defines platform-independent data contracts shared by:

- Facebook normalizers
- Instagram normalizers
- Customer-review normalizers
- Social storage services
- Trend-analysis services
- SWOT and strategy evidence builders

These schemas are transfer objects only. They are not SQLAlchemy
models and are not Beanie documents.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.common import BaseSchema


# ============================================================
# Shared Literal Types
# ============================================================
SocialPlatform = Literal[
    "facebook",
    "instagram",
    "linkedin",
    "tiktok",
    "youtube",
    "other",
]

ContentType = Literal[
    "text",
    "image",
    "video",
    "carousel",
    "reel",
    "story",
    "link",
    "live",
    "unknown",
]

CustomerVoiceSource = Literal[
    "google_maps",
    "facebook_comments",
    "facebook_reviews",
    "instagram_comments",
    "linkedin_comments",
    "tiktok_comments",
    "website_reviews",
    "other",
]

InformationQuality = Literal[
    "high",
    "medium",
    "low",
]

SourceRole = Literal[
    "primary_customer_voice",
    "supporting_customer_voice",
    "fallback_customer_voice",
    "social_content",
    "audience_response",
]

ConfidenceLevel = Literal[
    "high",
    "medium",
    "low",
    "insufficient",
]


# ============================================================
# Shared Normalization Helpers
# ============================================================
def normalize_optional_text(
    value: object,
) -> object:
    """
    Strip optional text and convert empty strings to None.
    """

    if not isinstance(value, str):
        return value

    normalized = value.strip()

    return normalized or None


def normalize_required_text(
    value: object,
) -> object:
    """
    Strip required text.

    Pydantic's min_length validation rejects the result if it
    becomes empty after stripping.
    """

    if isinstance(value, str):
        return value.strip()

    return value


def normalize_string_list(
    values: object,
) -> object:
    """
    Normalize a string list while preserving original order.

    Behavior:
    - Removes empty values.
    - Strips whitespace.
    - Removes a leading # from hashtags.
    - Removes a leading @ from mentions.
    - Deduplicates values case-insensitively.
    """

    if values is None:
        return []

    if not isinstance(values, list):
        return values

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        normalized = value.strip()

        if normalized.startswith(("#", "@")):
            normalized = normalized[1:].strip()

        if not normalized:
            continue

        deduplication_key = normalized.casefold()

        if deduplication_key in seen:
            continue

        seen.add(deduplication_key)
        normalized_values.append(normalized)

    return normalized_values


# ============================================================
# Normalized Social Metrics
# ============================================================
class NormalizedSocialMetrics(BaseSchema):
    """
    Platform-independent social engagement metrics.

    Missing values remain None instead of being converted to zero.

    Facebook reactions are kept separately from likes because
    reactions may include several reaction types, not likes only.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    likes: int | None = Field(
        default=None,
        ge=0,
    )

    reactions: int | None = Field(
        default=None,
        ge=0,
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

    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def normalize_captured_at(
        cls,
        value: datetime,
    ) -> datetime:
        """Return a timezone-aware UTC observation time."""

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


# ============================================================
# Normalized Social Post
# ============================================================
class NormalizedSocialPost(BaseSchema):
    """
    Platform-independent social post produced by a normalizer.

    The normalizer does not determine business ownership.
    business_id and social_account_id are supplied by the secured
    collection workflow.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    business_id: UUID

    social_account_id: UUID

    platform: SocialPlatform

    platform_post_id: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    published_at: datetime | None = None

    text: str | None = None

    content_type: ContentType = "unknown"

    post_url: str | None = Field(
        default=None,
        max_length=2000,
    )

    hashtags: list[str] = Field(
        default_factory=list,
    )

    mentions: list[str] = Field(
        default_factory=list,
    )

    tagged_accounts: list[str] = Field(
        default_factory=list,
    )

    media_urls: list[str] = Field(
        default_factory=list,
    )

    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )

    location_name: str | None = Field(
        default=None,
        max_length=500,
    )

    is_pinned: bool | None = None

    metrics: NormalizedSocialMetrics

    connector_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,49}$",
    )

    raw_data: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "platform_post_id",
        mode="before",
    )
    @classmethod
    def normalize_platform_post_id(
        cls,
        value: object,
    ) -> object:
        """
        Strip the platform post ID without changing its case.
        """

        return normalize_required_text(value)

    @field_validator(
        "connector_type",
        mode="before",
    )
    @classmethod
    def normalize_connector_type(
        cls,
        value: object,
    ) -> object:
        """Normalize connector identifiers to lowercase."""

        normalized = normalize_required_text(value)

        if isinstance(normalized, str):
            return normalized.lower()

        return normalized

    @field_validator(
        "text",
        "post_url",
        "language",
        "location_name",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(
        cls,
        value: object,
    ) -> object:
        """Normalize optional textual values."""

        return normalize_optional_text(value)

    @field_validator(
        "hashtags",
        "mentions",
        "tagged_accounts",
        "media_urls",
        mode="before",
    )
    @classmethod
    def normalize_lists(
        cls,
        values: object,
    ) -> object:
        """Normalize ordered string collections."""

        return normalize_string_list(values)

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Normalize publication timestamps to UTC."""

        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


# ============================================================
# Normalized Social Comment
# ============================================================
class NormalizedSocialComment(BaseSchema):
    """
    Platform-independent audience comment.

    Personal profile details are intentionally minimized.
    The normalized contract does not contain profile photos,
    gender, work information, or full raw author profiles.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    business_id: UUID

    social_account_id: UUID

    platform: SocialPlatform

    platform_post_id: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    platform_comment_id: str | None = Field(
        default=None,
        max_length=500,
    )

    text: str = Field(
        ...,
        min_length=1,
    )

    published_at: datetime | None = None

    like_count: int | None = Field(
        default=None,
        ge=0,
    )

    reply_count: int | None = Field(
        default=None,
        ge=0,
    )

    author_reference: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "A minimized platform author identifier or username. "
            "It must not contain a full author profile."
        ),
    )

    information_quality: InformationQuality

    is_emoji_only: bool = False

    connector_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,49}$",
    )

    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "A minimized raw comment payload. "
            "Unnecessary personal profile data must be removed."
        ),
    )

    @field_validator(
        "platform_post_id",
        "platform_comment_id",
        "author_reference",
        mode="before",
    )
    @classmethod
    def normalize_external_references(
        cls,
        value: object,
    ) -> object:
        """
        Strip external identifiers without changing their case.
        """

        return normalize_optional_text(value)

    @field_validator(
        "connector_type",
        mode="before",
    )
    @classmethod
    def normalize_comment_connector(
        cls,
        value: object,
    ) -> object:
        """Normalize the connector identifier to lowercase."""

        normalized = normalize_required_text(value)

        if isinstance(normalized, str):
            return normalized.lower()

        return normalized

    @field_validator("text", mode="before")
    @classmethod
    def normalize_comment_text(
        cls,
        value: object,
    ) -> object:
        """Normalize required comment text."""

        return normalize_required_text(value)

    @field_validator("published_at")
    @classmethod
    def normalize_comment_time(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Normalize comment publication time to UTC."""

        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


# ============================================================
# Normalized Customer Review
# ============================================================
class NormalizedCustomerReview(BaseSchema):
    """
    Normalized customer-experience review.

    This contract is separate from social comments because a
    location review and a social reaction represent different
    types of evidence.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    business_id: UUID

    source: CustomerVoiceSource

    source_review_id: str | None = Field(
        default=None,
        max_length=500,
    )

    text: str = Field(
        ...,
        min_length=1,
    )

    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )

    rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    published_at: datetime | None = None

    collected_at: datetime

    information_quality: InformationQuality

    is_meaningful: bool

    is_emoji_only: bool = False

    raw_data: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "source_review_id",
        "language",
        mode="before",
    )
    @classmethod
    def normalize_review_optional_text(
        cls,
        value: object,
    ) -> object:
        """Normalize optional review text fields."""

        return normalize_optional_text(value)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_review_text(
        cls,
        value: object,
    ) -> object:
        """Normalize required customer-review text."""

        return normalize_required_text(value)

    @field_validator(
        "published_at",
        "collected_at",
    )
    @classmethod
    def normalize_review_time(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Normalize customer-review timestamps to UTC."""

        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


# ============================================================
# Source Quality Assessment
# ============================================================
class SourceQualityAssessment(BaseSchema):
    """
    Quality assessment used to choose customer-voice sources.

    This model does not decide the source by itself.
    A later source-selection service will calculate and compare
    assessments for all available sources.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    source: CustomerVoiceSource

    source_role: SourceRole

    available: bool

    sample_size: int = Field(
        ...,
        ge=0,
    )

    meaningful_sample_count: int = Field(
        ...,
        ge=0,
    )

    emoji_only_count: int = Field(
        default=0,
        ge=0,
    )

    meaningful_text_ratio: float = Field(
        ...,
        ge=0,
        le=1,
    )

    emoji_only_ratio: float = Field(
        ...,
        ge=0,
        le=1,
    )

    has_ratings: bool = False

    has_publication_dates: bool = False

    confidence: ConfidenceLevel

    notes: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_counts(
        self,
    ) -> "SourceQualityAssessment":
        """Ensure source-quality counts are internally consistent."""

        if self.meaningful_sample_count > self.sample_size:
            raise ValueError(
                "meaningful_sample_count cannot exceed sample_size"
            )

        if self.emoji_only_count > self.sample_size:
            raise ValueError(
                "emoji_only_count cannot exceed sample_size"
            )

        if not self.available and self.sample_size > 0:
            raise ValueError(
                "An unavailable source cannot have samples"
            )

        return self
