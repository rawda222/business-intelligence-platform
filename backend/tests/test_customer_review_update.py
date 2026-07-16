"""
Customer Review Safe Update Tests

Verifies safe field updates while preserving identity, existing
useful values, and raw_data across repeated observations.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.schemas.normalized_social import (
    NormalizedCustomerReview,
)
from app.services.customer_review_storage_service import (
    build_customer_review_deduplication_key,
    create_customer_review,
    update_customer_review_safely,
)


def build_original_review(
    *,
    business_id,
    source_review_id: str | None,
) -> NormalizedCustomerReview:
    """Build the initial normalized review used for update tests."""

    return NormalizedCustomerReview(
        business_id=business_id,
        source="google_maps",
        source_review_id=source_review_id,
        text="الخدمة جيدة",
        language="ar",
        rating=4.0,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
        collected_at=datetime(
            2026,
            7,
            15,
            19,
            0,
            tzinfo=UTC,
        ),
        information_quality="medium",
        is_meaningful=True,
        is_emoji_only=False,
        raw_data={
            "source": "update_test",
            "original_key": "original_value",
        },
    )


@pytest.mark.asyncio
async def test_existing_review_is_updated_safely():
    """Update mutable fields without erasing existing values."""

    business_id = uuid4()

    original = build_original_review(
        business_id=business_id,
        source_review_id=(
            f"update-{uuid4().hex}"
        ),
    )

    deduplication_key = (
        build_customer_review_deduplication_key(
            original
        )
    )

    stored_review = None

    try:
        await connect_to_mongo()

        stored_review = await create_customer_review(
            review=original,
            deduplication_key=deduplication_key,
        )

        assert stored_review.id is not None

        # ====================================================
        # New Observation With Improved Fields
        # ====================================================
        updated = original.model_copy(
            update={
                "text": (
                    "الخدمة ممتازة "
                    "والقهوة رائعة"
                ),
                "language": None,
                "rating": 5.0,
                "information_quality": "high",
                "is_meaningful": True,
                "is_emoji_only": False,
                "raw_data": {
                    "new_key": "new_value",
                    "ignored_key": None,
                },
                "collected_at": datetime(
                    2026,
                    7,
                    16,
                    9,
                    0,
                    tzinfo=UTC,
                ),
            },
        )

        changed = (
            await update_customer_review_safely(
                stored_review=stored_review,
                incoming_review=updated,
            )
        )

        assert changed is True

        refreshed = (
            await CustomerReviewDocument.get(
                stored_review.id,
            )
        )

        assert refreshed is not None

        # Updated fields.
        assert (
            refreshed.text
            == (
                "الخدمة ممتازة "
                "والقهوة رائعة"
            )
        )

        assert refreshed.rating == 5.0

        assert (
            refreshed.information_quality
            == "high"
        )

        # None must not erase stored language.
        assert refreshed.language == "ar"

        # raw_data preserves original and adds new key.
        assert refreshed.raw_data == {
            "source": "update_test",
            "original_key": "original_value",
            "new_key": "new_value",
        }

        # Identity fields must remain unchanged.
        assert (
            refreshed.business_id
            == business_id
        )

        assert (
            refreshed.source
            == "google_maps"
        )

        assert (
            refreshed.source_review_id
            == original.source_review_id
        )

        assert (
            refreshed.deduplication_key
            == deduplication_key
        )

        # Collection timestamp advances only when changed.
        assert (
            refreshed.collected_at
            is not None
        )

    finally:
        try:
            if (
                stored_review is not None
                and stored_review.id is not None
            ):
                persisted_review = (
                    await CustomerReviewDocument.get(
                        stored_review.id
                    )
                )

                if persisted_review is not None:
                    await persisted_review.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_identical_observation_returns_false():
    """Return False when the incoming observation is identical."""

    business_id = uuid4()

    review = build_original_review(
        business_id=business_id,
        source_review_id=(
            f"identical-{uuid4().hex}"
        ),
    )

    deduplication_key = (
        build_customer_review_deduplication_key(
            review
        )
    )

    stored_review = None

    try:
        await connect_to_mongo()

        stored_review = await create_customer_review(
            review=review,
            deduplication_key=deduplication_key,
        )

        assert stored_review.id is not None

        changed = (
            await update_customer_review_safely(
                stored_review=stored_review,
                incoming_review=review,
            )
        )

        assert changed is False

        refreshed = (
            await CustomerReviewDocument.get(
                stored_review.id,
            )
        )

        assert refreshed is not None
        assert refreshed.text == review.text
        assert refreshed.language == "ar"
        assert refreshed.rating == 4.0

        assert (
            refreshed.information_quality
            == "medium"
        )

        assert refreshed.raw_data == {
            "source": "update_test",
            "original_key": "original_value",
        }

    finally:
        try:
            if (
                stored_review is not None
                and stored_review.id is not None
            ):
                persisted_review = (
                    await CustomerReviewDocument.get(
                        stored_review.id
                    )
                )

                if persisted_review is not None:
                    await persisted_review.delete()
        finally:
            await close_mongo()