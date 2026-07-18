"""
Mongo-Backed Cross-Source Customer Voice Loader

Loads tenant-scoped customer reviews and social comments from
MongoDB, then passes them to the pure cross-source customer-voice
service.

The loader:

- Requires one business_id.
- Applies a half-open UTC date range:
  range_start <= published_at < range_end.
- Loads CustomerReviewDocument records.
- Loads SocialCommentDocument records.
- Delegates supported-source filtering and deduplication to the
  pure cross-source customer-voice service.
- Does not load social posts as customer sentiment.
- Does not call an LLM.
"""

from datetime import UTC, datetime
from uuid import UUID
from typing import Any
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.services.cross_source_customer_voice_service import (
    CrossSourceCustomerVoiceResult,
    build_cross_source_customer_voice,
)


def _ensure_utc(
    value: datetime,
) -> datetime:
    """Return one timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC
        )

    return value.astimezone(
        UTC
    )


def _validate_range(
    *,
    range_start: datetime,
    range_end: datetime,
) -> tuple[
    datetime,
    datetime,
]:
    """Normalize and validate one half-open analysis range."""

    normalized_start = _ensure_utc(
        range_start
    )

    normalized_end = _ensure_utc(
        range_end
    )

    if normalized_start >= normalized_end:
        raise ValueError(
            "range_start must be earlier than range_end."
        )

    return (
        normalized_start,
        normalized_end,
    )


async def _load_customer_reviews(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[Any]:
    """Load business-scoped customer reviews in the date range."""

    return await CustomerReviewDocument.find(
        CustomerReviewDocument.business_id
        == business_id,
        CustomerReviewDocument.published_at
        >= range_start,
        CustomerReviewDocument.published_at
        < range_end,
    ).to_list()


async def _load_social_comments(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[Any]:
    """Load business-scoped social comments in the date range."""

    return await SocialCommentDocument.find(
        SocialCommentDocument.business_id
        == business_id,
        SocialCommentDocument.published_at
        >= range_start,
        SocialCommentDocument.published_at
        < range_end,
    ).to_list()


async def load_cross_source_customer_voice(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    range_start: datetime,
    range_end: datetime,
) -> CrossSourceCustomerVoiceResult:
    """
    Load and normalize customer voice for one business and range.

    Customer reviews are passed first so that, when one Facebook
    or Instagram comment exists in both MongoDB collections, the
    CustomerReviewDocument representation wins deterministically.
    """

    (
        normalized_start,
        normalized_end,
    ) = _validate_range(
        range_start=range_start,
        range_end=range_end,
    )

    customer_reviews = (
        await _load_customer_reviews(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
        )
    )

    social_comments = (
        await _load_social_comments(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
        )
    )

    return build_cross_source_customer_voice(
        business_id=business_id,
        business_name=business_name,
        business_type=business_type,
        customer_reviews=customer_reviews,
        social_comments=social_comments,
    )