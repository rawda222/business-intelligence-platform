"""
Customer Review Identity Tests

Verifies deterministic customer-review deduplication keys without
requiring a MongoDB connection.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.schemas.normalized_social import (
    NormalizedCustomerReview,
)
from app.services.customer_review_storage_service import (
    build_customer_review_deduplication_key,
)


BUSINESS_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)


def build_test_review(
    *,
    source_review_id: str | None,
    text: str = "الخدمة ممتازة",
    language: str | None = "ar",
    published_at: datetime | None = None,
) -> NormalizedCustomerReview:
    """Build one valid normalized customer review."""

    return NormalizedCustomerReview(
        business_id=BUSINESS_ID,
        source="google_maps",
        source_review_id=source_review_id,
        text=text,
        language=language,
        rating=5.0,
        published_at=(
            published_at
            or datetime(
                2026,
                7,
                15,
                18,
                0,
                tzinfo=UTC,
            )
        ),
        collected_at=datetime(
            2026,
            7,
            15,
            19,
            0,
            tzinfo=UTC,
        ),
        information_quality="high",
        is_meaningful=True,
        is_emoji_only=False,
        raw_data={
            "source": "identity_test",
        },
    )


def test_external_review_id_is_preferred():
    review = build_test_review(
        source_review_id="review-abc-123",
    )

    assert (
        build_customer_review_deduplication_key(
            review
        )
        == "id:review-abc-123"
    )


def test_external_review_id_is_trimmed():
    review = build_test_review(
        source_review_id=(
            "  review-abc-123  "
        ),
    )

    assert (
        build_customer_review_deduplication_key(
            review
        )
        == "id:review-abc-123"
    )


def test_missing_external_id_generates_stable_sha256():
    first = build_test_review(
        source_review_id=None,
    )

    second = build_test_review(
        source_review_id=None,
    )

    first_key = (
        build_customer_review_deduplication_key(
            first
        )
    )

    second_key = (
        build_customer_review_deduplication_key(
            second
        )
    )

    assert first_key == second_key

    assert first_key.startswith(
        "sha256:"
    )

    assert len(first_key) == (
        len("sha256:") + 64
    )


def test_fallback_identity_changes_when_text_changes():
    first = build_test_review(
        source_review_id=None,
        text="الخدمة ممتازة",
    )

    changed = build_test_review(
        source_review_id=None,
        text="الخدمة بطيئة",
    )

    assert (
        build_customer_review_deduplication_key(
            first
        )
        != build_customer_review_deduplication_key(
            changed
        )
    )


def test_fallback_identity_changes_when_language_changes():
    first = build_test_review(
        source_review_id=None,
        language="ar",
    )

    changed = build_test_review(
        source_review_id=None,
        language="en",
    )

    assert (
        build_customer_review_deduplication_key(
            first
        )
        != build_customer_review_deduplication_key(
            changed
        )
    )


def test_fallback_identity_changes_when_time_changes():
    first = build_test_review(
        source_review_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
    )

    changed = build_test_review(
        source_review_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            5,
            tzinfo=UTC,
        ),
    )

    assert (
        build_customer_review_deduplication_key(
            first
        )
        != build_customer_review_deduplication_key(
            changed
        )
    )


def test_fallback_identity_normalizes_datetime_to_utc():
    aware_review = build_test_review(
        source_review_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
    )

    naive_review = build_test_review(
        source_review_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
        ),
    )

    assert (
        build_customer_review_deduplication_key(
            aware_review
        )
        == build_customer_review_deduplication_key(
            naive_review
        )
    )


def test_missing_time_and_language_remain_deterministic():
    first = build_test_review(
        source_review_id=None,
        language=None,
        published_at=None,
    )

    second = build_test_review(
        source_review_id=None,
        language=None,
        published_at=None,
    )

    assert (
        build_customer_review_deduplication_key(
            first
        )
        == build_customer_review_deduplication_key(
            second
        )
    )


def test_very_long_external_id_is_hashed():
    review = build_test_review(
        source_review_id="x" * 300,
    )

    key = build_customer_review_deduplication_key(
        review
    )

    assert key.startswith(
        "id-sha256:"
    )

    assert len(key) == (
        len("id-sha256:") + 64
    )

    assert len(key) <= 128