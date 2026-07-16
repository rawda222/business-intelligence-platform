"""
Customer Review Payload Processing Tests

Verifies the complete customer-review payload workflow, including
normalization, batch storage, and source-quality assessment.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.services.customer_review_payload_processing_service import (
    process_customer_review_payload,
)


def build_volume_style_payload(
    *,
    unique_suffix: str,
) -> dict:
    """Return a Volume-style customer-review payload."""

    return {
        "reviews": {
            "summary": {
                "average_rating": 4.32,
                "total_reviews": 24,
            },
            "raw_samples": [
                {
                    "id": (
                        f"review-a-{unique_suffix}"
                    ),
                    "text": (
                        "{'ar': 'كل شيء لذيذ "
                        "والفيو مره حلو "
                        "والخدمه ممتازه'}"
                    ),
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": (
                        f"review-b-{unique_suffix}"
                    ),
                    "text": (
                        "{'ar': 'المكان جميل "
                        "ولكنه مزدحم جدا "
                        "والخدمة بطيئة "
                        "لكن الاكل لذيذ'}"
                    ),
                    "rating": 4,
                    "source": "google_maps",
                },
                {
                    "id": (
                        f"review-c-{unique_suffix}"
                    ),
                    "text": "😍😍😍",
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": (
                        f"review-empty-"
                        f"{unique_suffix}"
                    ),
                    "text": "   ",
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": (
                        f"review-invalid-rating-"
                        f"{unique_suffix}"
                    ),
                    "text": (
                        "المكان جميل والقهوة "
                        "جيدة والخدمة سريعة"
                    ),
                    "rating": 7,
                    "source": "google_maps",
                },
            ],
        },
    }


@pytest.mark.asyncio
async def test_review_payload_normalizes_and_persists():
    """
    Normalize and store customer reviews from a Volume-style payload.

    Empty text is skipped by the normalizer. Rating 7 is rejected as
    invalid but the review text is preserved. Two rerun executions
    must remain idempotent.
    """

    business_id = uuid4()
    unique_suffix = uuid4().hex

    payload = build_volume_style_payload(
        unique_suffix=unique_suffix,
    )

    explicit_collected_at = datetime(
        2026,
        7,
        15,
        18,
        0,
        tzinfo=UTC,
    )

    stored_review_ids = []

    try:
        await connect_to_mongo()

        first_result = (
            await process_customer_review_payload(
                payload,
                business_id=business_id,
                source="google_maps",
                collected_at=(
                    explicit_collected_at
                ),
            )
        )

        stored_review_ids = [
            result.review.id
            for result in (
                first_result.storage.results
            )
            if result.review.id is not None
        ]

        # ====================================================
        # Normalization
        # ====================================================
        assert (
            first_result.source
            == "google_maps"
        )

        # Empty text is skipped.
        # Emoji-only review is kept but not meaningful.
        # Invalid rating is nullified but text is kept.
        assert (
            first_result.reviews_normalized
            == 4
        )

        # ====================================================
        # Storage
        # ====================================================
        assert (
            first_result.reviews_persisted
            == 4
        )

        assert (
            first_result.storage.reviews_created
            == 4
        )

        assert (
            first_result.storage.reviews_updated
            == 0
        )

        assert (
            first_result.storage.reviews_unchanged
            == 0
        )

        assert (
            first_result.storage.failures
            == []
        )

        # ====================================================
        # Source Quality
        # ====================================================
        assert (
            first_result.assessment.source
            == "google_maps"
        )

        assert (
            first_result.assessment.available
            is True
        )

        assert (
            first_result.assessment.sample_size
            == 4
        )

        assert (
            first_result.assessment.emoji_only_count
            >= 1
        )

        # ====================================================
        # Second Run: Idempotency
        # ====================================================
        second_result = (
            await process_customer_review_payload(
                payload,
                business_id=business_id,
                source="google_maps",
                collected_at=(
                    explicit_collected_at
                ),
            )
        )

        assert (
            second_result.reviews_normalized
            == 4
        )

        assert (
            second_result.reviews_persisted
            == 4
        )

        assert (
            second_result.storage.reviews_created
            == 0
        )

        assert (
            second_result.storage.reviews_updated
            + second_result.storage.reviews_unchanged
            == 4
        )

        assert (
            second_result.storage.failures
            == []
        )

        stored_count = await (
            CustomerReviewDocument.find(
                CustomerReviewDocument.business_id
                == business_id,
                CustomerReviewDocument.source
                == "google_maps",
            ).count()
        )

        assert stored_count == 4

    finally:
        try:
            for review_id in stored_review_ids:
                persisted_review = (
                    await CustomerReviewDocument.get(
                        review_id
                    )
                )

                if persisted_review is not None:
                    await persisted_review.delete()
        finally:
            await close_mongo()