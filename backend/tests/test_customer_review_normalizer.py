"""
Customer Review Normalizer Tests

Verifies customer-review normalization and source-quality assessment
using structures that match the Volume Cafe business payload.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.preprocessing.customer_voice.review_normalizer import (
    assess_review_source_quality,
    determine_confidence,
    determine_source_role,
    extract_declared_total_reviews,
    extract_review_samples,
    is_meaningful_customer_review,
    normalize_and_assess_customer_reviews,
    normalize_customer_review,
    normalize_customer_review_payload,
    normalize_language_code,
    normalize_review_source,
    parse_review_rating,
    parse_review_text,
)


# ============================================================
# Shared Test Payload
# ============================================================
def build_customer_review_payload() -> dict:
    """
    Return a Volume-style customer-review payload.

    Includes:
    - Python-literal language dictionaries
    - JSON language dictionary
    - Plain text
    - Emoji-only review
    - Empty review
    - Invalid rating
    - Invalid non-dictionary record
    """

    return {
        "reviews": {
            "summary": {
                "average_rating": 4.32,
                "total_reviews": 24,
                "rating_distribution": {
                    "1_star": 1,
                    "2_star": 1,
                    "3_star": 1,
                    "4_star": 4,
                    "5_star": 17,
                },
            },
            "raw_samples": [
                {
                    "id": "ReviewCaseSensitiveA",
                    "text": (
                        "{'ar': 'كل شيء لذيذ "
                        "والفيو مره حلو والخدمه ممتازه'}"
                    ),
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": "ReviewCaseSensitiveB",
                    "text": (
                        "{'ar': 'المكان جميل ولكنه مزدحم جدا "
                        "والخدمة بطيئة لكن الاكل لذيذ'}"
                    ),
                    "rating": 4,
                    "source": "google_maps",
                },
                {
                    "id": "ReviewCaseSensitiveC",
                    "text": (
                        '{"en": "Beautiful place with '
                        'friendly staff and excellent coffee"}'
                    ),
                    "rating": "5",
                    "source": "Google Maps",
                },
                {
                    "id": "ReviewPlainText",
                    "text": (
                        "The view is beautiful but "
                        "the service is slow"
                    ),
                    "language": "EN",
                    "rating": "4.5",
                    "source": "googlemaps",
                    "published_at": (
                        "2026-07-10T12:00:00Z"
                    ),
                },
                {
                    "id": "EmojiReview",
                    "text": "😍😍😍",
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": "EmptyReview",
                    "text": "   ",
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": "InvalidRatingReview",
                    "text": (
                        "المكان جميل والقهوة جيدة "
                        "والخدمة سريعة"
                    ),
                    "rating": 7,
                    "source": "google_maps",
                },
                "invalid-review-record",
            ],
        },
    }


# ============================================================
# Complete Payload Tests
# ============================================================
def test_volume_style_payload_normalizes_review_samples():
    """Normalize the usable review records in a Volume payload."""

    business_id = uuid4()

    collected_at = datetime(
        2026,
        7,
        14,
        12,
        0,
        tzinfo=UTC,
    )

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=business_id,
        collected_at=collected_at,
    )

    assert len(reviews) == 6

    assert all(
        review.business_id == business_id
        for review in reviews
    )

    assert all(
        review.source == "google_maps"
        for review in reviews
    )

    assert all(
        review.collected_at == collected_at
        for review in reviews
    )


def test_python_literal_arabic_review_is_parsed():
    """Extract Arabic text and language from Python-literal format."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    review = reviews[0]

    assert (
        review.source_review_id
        == "ReviewCaseSensitiveA"
    )

    assert review.language == "ar"

    assert review.text == (
        "كل شيء لذيذ والفيو مره حلو "
        "والخدمه ممتازه"
    )

    assert review.rating == 5.0
    assert review.information_quality == "high"
    assert review.is_meaningful is True
    assert review.is_emoji_only is False


def test_json_language_dictionary_is_parsed():
    """Extract text from a valid JSON language dictionary."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    review = reviews[2]

    assert (
        review.source_review_id
        == "ReviewCaseSensitiveC"
    )

    assert review.language == "en"

    assert review.text == (
        "Beautiful place with friendly staff "
        "and excellent coffee"
    )

    assert review.rating == 5.0
    assert review.is_meaningful is True


def test_plain_text_and_explicit_language_are_preserved():
    """Keep plain review text and normalize explicit language."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    review = reviews[3]

    assert (
        review.source_review_id
        == "ReviewPlainText"
    )

    assert review.language == "en"

    assert review.text == (
        "The view is beautiful but "
        "the service is slow"
    )

    assert review.rating == 4.5

    assert review.published_at is not None
    assert review.published_at.tzinfo == UTC


def test_emoji_only_review_is_not_meaningful():
    """Keep emoji reactions without treating them as rich evidence."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    review = reviews[4]

    assert review.text == "😍😍😍"
    assert review.information_quality == "low"
    assert review.is_meaningful is False
    assert review.is_emoji_only is True
    assert review.rating == 5.0


def test_empty_and_invalid_records_are_skipped():
    """Skip empty text and non-dictionary review records."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    assert len(reviews) == 6

    review_ids = {
        review.source_review_id
        for review in reviews
    }

    assert "EmptyReview" not in review_ids

    assert all(
        review.text.strip()
        for review in reviews
    )


def test_invalid_rating_does_not_delete_valid_text():
    """Keep useful text even when the rating is invalid."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    review = reviews[5]

    assert (
        review.source_review_id
        == "InvalidRatingReview"
    )

    assert review.rating is None
    assert review.is_meaningful is True

    assert review.text == (
        "المكان جميل والقهوة جيدة "
        "والخدمة سريعة"
    )


def test_review_raw_data_is_minimized():
    """Do not duplicate the serialized review text in raw_data."""

    reviews = normalize_customer_review_payload(
        build_customer_review_payload(),
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    raw_data = reviews[0].raw_data

    assert raw_data == {
        "source": "google_maps",
        "source_review_id": (
            "ReviewCaseSensitiveA"
        ),
    }

    assert "text" not in raw_data
    assert "rating" not in raw_data


# ============================================================
# Quality Assessment Tests
# ============================================================
def test_google_maps_quality_assessment_uses_available_samples():
    """
    Assess only normalized text samples, not the aggregate total.
    """

    reviews, assessment = (
        normalize_and_assess_customer_reviews(
            build_customer_review_payload(),
            business_id=uuid4(),
            collected_at=datetime.now(UTC),
        )
    )

    assert len(reviews) == 6

    assert assessment.source == "google_maps"
    assert assessment.available is True

    assert assessment.sample_size == 6
    assert assessment.meaningful_sample_count == 5
    assert assessment.emoji_only_count == 1

    assert assessment.meaningful_text_ratio == pytest.approx(
        5 / 6
    )

    assert assessment.emoji_only_ratio == pytest.approx(
        1 / 6
    )

    assert assessment.has_ratings is True

    assert (
        assessment.has_publication_dates
        is True
    )

    assert (
        assessment.source_role
        == "primary_customer_voice"
    )

    assert assessment.confidence == "medium"

    assert (
        "Declared platform total reviews: 24"
        in assessment.notes
    )

    assert (
        "Quality assessment uses the available "
        "normalized sample size: 6"
        in assessment.notes
    )

    assert (
        "Emoji-only samples: 1"
        in assessment.notes
    )


def test_empty_source_has_insufficient_confidence():
    """No normalized samples produces an unavailable source."""

    assessment = assess_review_source_quality(
        [],
        source="google_maps",
        declared_total_reviews=0,
    )

    assert assessment.available is False
    assert assessment.sample_size == 0
    assert assessment.meaningful_sample_count == 0
    assert assessment.emoji_only_count == 0
    assert assessment.meaningful_text_ratio == 0.0
    assert assessment.emoji_only_ratio == 0.0

    assert (
        assessment.source_role
        == "fallback_customer_voice"
    )

    assert assessment.confidence == "insufficient"


def test_declared_total_is_extracted_separately():
    """Read the aggregate count without using it as sample size."""

    payload = build_customer_review_payload()

    assert (
        extract_declared_total_reviews(payload)
        == 24
    )

    assert (
        len(extract_review_samples(payload))
        == 7
    )


# ============================================================
# Safe Text Parsing Tests
# ============================================================
@pytest.mark.parametrize(
    (
        "value",
        "explicit_language",
        "expected_text",
        "expected_language",
    ),
    [
        (
            "{'ar': 'الخدمة ممتازة'}",
            None,
            "الخدمة ممتازة",
            "ar",
        ),
        (
            '{"en": "Excellent coffee"}',
            None,
            "Excellent coffee",
            "en",
        ),
        (
            {
                "ar": "المكان جميل",
            },
            None,
            "المكان جميل",
            "ar",
        ),
        (
            "Plain customer review",
            "EN",
            "Plain customer review",
            "en",
        ),
        (
            "{'ar': 'النص العربي'}",
            "en",
            "النص العربي",
            "en",
        ),
    ],
)
def test_review_text_parsing(
    value,
    explicit_language,
    expected_text,
    expected_language,
):
    """Parse supported review representations."""

    parsed = parse_review_text(
        value,
        explicit_language=explicit_language,
    )

    assert parsed is not None
    assert parsed.text == expected_text
    assert parsed.language == expected_language


def test_malformed_mapping_is_treated_as_plain_text():
    """A malformed dictionary-like string must not execute."""

    malicious_text = (
        "{__import__('os').system('echo unsafe'): 'x'}"
    )

    parsed = parse_review_text(
        malicious_text
    )

    assert parsed is not None

    # literal_eval cannot execute this expression.
    # The original content remains ordinary text.
    assert parsed.text == malicious_text
    assert parsed.language is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ({}, None),
        ({"ar": "   "}, None),
    ],
)
def test_empty_review_text_returns_none(
    value,
    expected,
):
    """Empty or unusable content must be skipped."""

    assert parse_review_text(value) is expected


# ============================================================
# Rating and Source Tests
# ============================================================
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, 5.0),
        ("5", 5.0),
        ("4.5", 4.5),
        (0, 0.0),
        (None, None),
        (True, None),
        (-1, None),
        (6, None),
        ("invalid", None),
    ],
)
def test_review_rating_parsing(
    value,
    expected,
):
    """Parse valid ratings and reject invalid values."""

    assert parse_review_rating(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("google_maps", "google_maps"),
        ("Google Maps", "google_maps"),
        ("googlemaps", "google_maps"),
        (
            "facebook recommendations",
            "facebook_reviews",
        ),
        (
            "Instagram Comments",
            "instagram_comments",
        ),
        ("unknown_source", "other"),
        (None, "other"),
    ],
)
def test_review_source_normalization(
    value,
    expected,
):
    """Normalize supported customer-voice source names."""

    assert normalize_review_source(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AR", "ar"),
        ("en-US", "en-us"),
        (" en ", "en"),
        ("", None),
        ("x", None),
        (None, None),
        ("language-code-that-is-too-long", None),
    ],
)
def test_language_code_normalization(
    value,
    expected,
):
    """Normalize reasonable language codes."""

    assert normalize_language_code(value) == expected


# ============================================================
# Policy Boundary Tests
# ============================================================
@pytest.mark.parametrize(
    (
        "available",
        "sample_size",
        "meaningful_ratio",
        "expected",
    ),
    [
        (False, 0, 0.0, "insufficient"),
        (True, 1, 1.0, "low"),
        (True, 5, 0.5, "medium"),
        (True, 9, 1.0, "medium"),
        (True, 10, 0.7, "high"),
        (True, 10, 0.69, "medium"),
    ],
)
def test_confidence_policy(
    available,
    sample_size,
    meaningful_ratio,
    expected,
):
    """Verify confidence thresholds explicitly."""

    assert determine_confidence(
        available=available,
        sample_size=sample_size,
        meaningful_text_ratio=meaningful_ratio,
    ) == expected


@pytest.mark.parametrize(
    (
        "source",
        "available",
        "sample_size",
        "meaningful_ratio",
        "expected",
    ),
    [
        (
            "google_maps",
            True,
            5,
            0.5,
            "primary_customer_voice",
        ),
        (
            "google_maps",
            True,
            4,
            1.0,
            "supporting_customer_voice",
        ),
        (
            "google_maps",
            False,
            0,
            0.0,
            "fallback_customer_voice",
        ),
        (
            "instagram_comments",
            True,
            3,
            0.5,
            "supporting_customer_voice",
        ),
        (
            "instagram_comments",
            True,
            3,
            0.2,
            "fallback_customer_voice",
        ),
    ],
)
def test_source_role_policy(
    source,
    available,
    sample_size,
    meaningful_ratio,
    expected,
):
    """Verify source-role thresholds explicitly."""

    assert determine_source_role(
        source=source,
        available=available,
        sample_size=sample_size,
        meaningful_text_ratio=meaningful_ratio,
    ) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "المكان جميل والخدمة ممتازة",
            True,
        ),
        (
            "Beautiful place",
            True,
        ),
        (
            "رائع",
            False,
        ),
        (
            "😍😍😍",
            False,
        ),
        (
            "!!!",
            False,
        ),
    ],
)
def test_customer_review_meaningfulness(
    text,
    expected,
):
    """Distinguish rich evidence from lightweight reactions."""

    assert (
        is_meaningful_customer_review(text)
        is expected
    )


# ============================================================
# Single Review Test
# ============================================================
def test_single_review_preserves_case_and_invalid_rating():
    """Keep external ID case and useful text independently."""

    review = normalize_customer_review(
        {
            "id": "ReviewCaseSensitiveXYZ",
            "text": "{'ar': 'القهوة ممتازة والخدمة سريعة'}",
            "rating": 8,
            "source": "google_maps",
        },
        business_id=uuid4(),
        collected_at=datetime.now(UTC),
    )

    assert review is not None

    assert (
        review.source_review_id
        == "ReviewCaseSensitiveXYZ"
    )

    assert review.language == "ar"
    assert review.rating is None
    assert review.is_meaningful is True