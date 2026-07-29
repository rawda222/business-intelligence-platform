"""
Raw Customer Voice Adapter

Builds a CrossSourceCustomerVoiceResult directly from raw scraper
data, without reading from MongoDB.

Each raw sample is mapped into a customer-review-like or
social-comment-like record that the pure cross-source customer
voice service can consume.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.cross_source_customer_voice_service import (
    CrossSourceCustomerVoiceResult,
    build_cross_source_customer_voice,
)


_GOOGLE_SOURCES = {
    "google_maps",
    "google",
    "google_maps_reviews",
}

_FACEBOOK_SOURCES = {
    "facebook",
    "facebook_comments",
}

_INSTAGRAM_SOURCES = {
    "instagram",
    "instagram_comments",
}


def _extract_raw_samples(
    raw_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Find raw customer records across supported input shapes."""

    reviews_block = raw_data.get(
        "reviews",
        {},
    )

    if isinstance(reviews_block, dict):
        samples = reviews_block.get(
            "raw_samples",
            [],
        )
        if samples:
            return list(samples)

    if raw_data.get("raw_samples"):
        return list(
            raw_data["raw_samples"]
        )

    if raw_data.get("business_reviews"):
        return list(
            raw_data["business_reviews"]
        )

    return []


def _dedupe(
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact duplicate records by text and source."""

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for sample in samples:
        if not isinstance(sample, dict):
            continue

        text = str(
            sample.get("text", "")
        ).strip()

        source = str(
            sample.get(
                "source",
                "",
            )
            or sample.get(
                "platform",
                "",
            )
        ).strip().casefold()

        if not text:
            continue

        key = (
            text.casefold(),
            source,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(sample)

    return unique


def build_customer_voice_from_raw_data(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    raw_data: dict[str, Any],
) -> CrossSourceCustomerVoiceResult:
    """
    Build customer voice directly from raw scraper samples.

    Google Maps records become customer reviews. Facebook and
    Instagram records become social comments with a usable
    information-quality level so they are not filtered out.
    """

    samples = _dedupe(
        _extract_raw_samples(raw_data)
    )

    customer_reviews: list[dict[str, Any]] = []
    social_comments: list[dict[str, Any]] = []

    for index, sample in enumerate(
        samples
    ):
        text = str(
            sample.get("text", "")
        ).strip()

        if not text:
            continue

        source = str(
            sample.get("source", "")
            or sample.get("platform", "")
        ).strip().casefold()

        dedup_key = f"raw-{index}-{business_id}"

        if source in _GOOGLE_SOURCES:
            customer_reviews.append(
                {
                    "business_id": business_id,
                    "source": "google_maps",
                    "text": text,
                    "rating": sample.get(
                        "rating"
                    ),
                    "source_review_id": (
                        f"raw-review-{index}"
                    ),
                    "deduplication_key": (
                        dedup_key
                    ),
                    "is_emoji_only": False,
                    "is_meaningful": True,
                }
            )
            continue

        if source in _FACEBOOK_SOURCES:
            platform = "facebook"
        elif source in _INSTAGRAM_SOURCES:
            platform = "instagram"
        else:
            platform = "instagram"

        social_comments.append(
            {
                "business_id": business_id,
                "platform": platform,
                "text": text,
                "information_quality": (
                    "medium"
                ),
                "is_emoji_only": False,
                "platform_comment_id": (
                    f"raw-comment-{index}"
                ),
                "deduplication_key": (
                    dedup_key
                ),
            }
        )

    return build_cross_source_customer_voice(
        business_id=business_id,
        business_name=business_name,
        business_type=business_type,
        customer_reviews=customer_reviews,
        social_comments=social_comments,
    )