"""
Cross-Source Customer Voice Service Tests
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.cross_source_customer_voice_service import (
    build_cross_source_customer_voice,
)


_BUSINESS_ID = UUID(
    "12121212-1212-1212-1212-121212121212"
)

_OTHER_BUSINESS_ID = UUID(
    "34343434-3434-3434-3434-343434343434"
)


def _review(
    *,
    source: str,
    source_review_id: str | None,
    deduplication_key: str,
    text: str,
    rating: float | None = None,
    is_meaningful: bool = True,
    is_emoji_only: bool = False,
    business_id: UUID = _BUSINESS_ID,
):
    """Build a CustomerReviewDocument-like value."""

    return SimpleNamespace(
        business_id=business_id,
        source=source,
        source_review_id=(
            source_review_id
        ),
        deduplication_key=(
            deduplication_key
        ),
        text=text,
        rating=rating,
        information_quality="high",
        is_meaningful=is_meaningful,
        is_emoji_only=is_emoji_only,
    )


def _comment(
    *,
    platform: str,
    platform_comment_id: str | None,
    deduplication_key: str,
    text: str,
    information_quality: str = "high",
    is_emoji_only: bool = False,
    business_id: UUID = _BUSINESS_ID,
):
    """Build a SocialCommentDocument-like value."""

    return SimpleNamespace(
        business_id=business_id,
        platform=platform,
        platform_comment_id=(
            platform_comment_id
        ),
        deduplication_key=(
            deduplication_key
        ),
        text=text,
        information_quality=(
            information_quality
        ),
        is_emoji_only=is_emoji_only,
    )


def test_combines_google_facebook_and_instagram_voice():
    """All supported sources should enter one normalized envelope."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="google_maps",
                source_review_id="g-1",
                deduplication_key="g-key-1",
                text="Excellent coffee and friendly staff",
                rating=5,
            ),
        ],
        social_comments=[
            _comment(
                platform="facebook",
                platform_comment_id="f-1",
                deduplication_key="f-key-1",
                text="Service was very slow",
            ),
            _comment(
                platform="instagram",
                platform_comment_id="i-1",
                deduplication_key="i-key-1",
                text="The dessert was amazing",
            ),
        ],
    )

    assert result.records_received == 3

    assert result.records_included == 3

    assert result.records_excluded == 0

    assert result.duplicate_records == 0

    assert result.records_by_source == (
        (
            "google_maps",
            1,
        ),
        (
            "facebook_comments",
            1,
        ),
        (
            "instagram_comments",
            1,
        ),
    )

    assert [
        record["review_id"]
        for record in result.business_reviews
    ] == [
        "google_maps:review:g-1",
        "facebook:comment:f-1",
        "instagram:comment:i-1",
    ]


def test_existing_normalizer_adds_sentiment_hints():
    """Customer voice should reuse existing rating and text sentiment."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="google_maps",
                source_review_id="g-1",
                deduplication_key="g-key-1",
                text="Average experience",
                rating=1,
            ),
        ],
        social_comments=[
            _comment(
                platform="facebook",
                platform_comment_id="f-1",
                deduplication_key="f-key-1",
                text="Excellent and amazing service",
            ),
        ],
    )

    google_review = (
        result.business_reviews[0]
    )

    facebook_comment = (
        result.business_reviews[1]
    )

    assert (
        google_review["sentiment_hint"]
        == "negative"
    )

    assert (
        facebook_comment[
            "sentiment_hint"
        ]
        == "positive"
    )


def test_duplicate_comment_across_collections_is_counted_once():
    """
    A social comment stored as customer voice and social comment
    must not double the theme frequency.
    """

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="facebook_comments",
                source_review_id="shared-1",
                deduplication_key=(
                    "customer-key"
                ),
                text="Slow delivery",
            ),
        ],
        social_comments=[
            _comment(
                platform="facebook",
                platform_comment_id="shared-1",
                deduplication_key=(
                    "social-key"
                ),
                text="Slow delivery",
            ),
        ],
    )

    assert result.records_received == 2

    assert result.records_included == 1

    assert result.duplicate_records == 1

    assert len(
        result.business_reviews
    ) == 1

    assert (
        result.business_reviews[0][
            "review_id"
        ]
        == "facebook:comment:shared-1"
    )


def test_fallback_deduplication_key_is_traceable():
    """Missing external IDs should use the stored deduplication key."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        social_comments=[
            _comment(
                platform="instagram",
                platform_comment_id=None,
                deduplication_key="stable-key",
                text="Good menu variety",
            ),
        ],
    )

    record = result.business_reviews[0]

    assert (
        record["review_id"]
        == "instagram:comment:stable-key"
    )

    assert (
        record["evidence_reference"]
        == "instagram:comment:stable-key"
    )


def test_low_quality_and_emoji_only_records_are_excluded():
    """Unusable social text must not affect themes or sentiment."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="google_maps",
                source_review_id="g-emoji",
                deduplication_key="g-key",
                text="😀😀",
                is_emoji_only=True,
            ),
        ],
        social_comments=[
            _comment(
                platform="facebook",
                platform_comment_id="f-low",
                deduplication_key="f-key",
                text="ok",
                information_quality="low",
            ),
        ],
    )

    assert result.records_received == 2

    assert result.records_included == 0

    assert result.records_excluded == 2

    assert result.business_reviews == ()

    assert "emoji_only_review" in (
        result.warnings
    )

    assert "low_quality_comment" in (
        result.warnings
    )


def test_non_meaningful_customer_review_is_excluded():
    """A stored non-meaningful review should not enter Theme Extractor."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="google_maps",
                source_review_id="g-1",
                deduplication_key="g-key",
                text="ok",
                is_meaningful=False,
            ),
        ],
    )

    assert result.records_included == 0

    assert result.records_excluded == 1

    assert (
        "non_meaningful_review"
        in result.warnings
    )


def test_unsupported_sources_are_excluded():
    """Unapproved platforms should not enter the SWOT customer voice."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="website_reviews",
                source_review_id="w-1",
                deduplication_key="w-key",
                text="Website review",
            ),
        ],
        social_comments=[
            _comment(
                platform="linkedin",
                platform_comment_id="l-1",
                deduplication_key="l-key",
                text="LinkedIn comment",
            ),
        ],
    )

    assert result.records_included == 0

    assert result.records_excluded == 2

    assert (
        "unsupported_review_source"
        in result.warnings
    )

    assert (
        "unsupported_comment_platform"
        in result.warnings
    )


def test_cross_business_customer_review_is_rejected():
    """A review from another tenant must fail closed."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_cross_source_customer_voice(
            business_id=_BUSINESS_ID,
            business_name="Example Cafe",
            business_type="cafe",
            customer_reviews=[
                _review(
                    source="google_maps",
                    source_review_id="g-1",
                    deduplication_key="g-key",
                    text="Excellent",
                    business_id=(
                        _OTHER_BUSINESS_ID
                    ),
                ),
            ],
        )


def test_cross_business_social_comment_is_rejected():
    """A social comment from another tenant must fail closed."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_cross_source_customer_voice(
            business_id=_BUSINESS_ID,
            business_name="Example Cafe",
            business_type="cafe",
            social_comments=[
                _comment(
                    platform="facebook",
                    platform_comment_id="f-1",
                    deduplication_key="f-key",
                    text="Excellent",
                    business_id=(
                        _OTHER_BUSINESS_ID
                    ),
                ),
            ],
        )


def test_result_is_ready_for_existing_theme_extractor():
    """The output envelope should match collect_all_reviews()."""

    result = build_cross_source_customer_voice(
        business_id=_BUSINESS_ID,
        business_name="Example Cafe",
        business_type="cafe",
        customer_reviews=[
            _review(
                source="google_maps",
                source_review_id="g-1",
                deduplication_key="g-key",
                text="Great product quality",
                rating=5,
            ),
        ],
    )

    envelope = (
        result.as_theme_extractor_input()
    )

    assert envelope["business_name"] == (
        "Example Cafe"
    )

    assert envelope["business_type"] == (
        "cafe"
    )

    assert len(
        envelope["business_reviews"]
    ) == 1

    record = envelope[
        "business_reviews"
    ][0]

    assert record["entity_type"] == (
        "target_business"
    )

    assert record["usable_for_analysis"]

    assert record["source"] == (
        "google_maps"
    )