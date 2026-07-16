"""
Customer Review Creation Tests

Verifies persistence of one normalized customer review and unique
index protection against duplicate inserts.
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
    CustomerReviewAlreadyExistsError,
    build_customer_review_deduplication_key,
    create_customer_review,
)


def build_create_review(
    *,
    business_id,
    source: str,
    source_review_id: str | None,
) -> NormalizedCustomerReview:
    """Build one normalized review for creation tests."""

    return NormalizedCustomerReview(
        business_id=business_id,
        source=source,
        source_review_id=source_review_id,
        text="الخدمة ممتازة وسريعة والقهوة رائعة",
        language="ar",
        rating=5.0,
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
        information_quality="high",
        is_meaningful=True,
        is_emoji_only=False,
        raw_data={
            "source": "create_test",
        },
    )


@pytest.mark.asyncio
async def test_customer_review_is_created_correctly():
    """Persist one normalized customer review with correct fields."""

    business_id = uuid4()

    review = build_create_review(
        business_id=business_id,
        source="google_maps",
        source_review_id=(
            f"review-{uuid4().hex}"
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

        assert (
            stored_review.business_id
            == business_id
        )

        assert (
            stored_review.source
            == "google_maps"
        )

        assert (
            stored_review.deduplication_key
            == deduplication_key
        )

        assert (
            stored_review.source_review_id
            == review.source_review_id
        )

        assert (
            stored_review.text
            == review.text
        )

        assert (
            stored_review.language
            == "ar"
        )

        assert stored_review.rating == 5.0

        assert (
            stored_review.information_quality
            == "high"
        )

        assert (
            stored_review.is_meaningful
            is True
        )

        assert (
            stored_review.is_emoji_only
            is False
        )

        assert stored_review.raw_data == {
            "source": "create_test",
        }

        assert (
            stored_review.published_at
            is not None
        )

        assert (
            stored_review.collected_at
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
async def test_duplicate_customer_review_is_rejected():
    """Reject a second insert that violates the unique review index."""

    business_id = uuid4()

    review = build_create_review(
        business_id=business_id,
        source="google_maps",
        source_review_id=(
            f"duplicate-{uuid4().hex}"
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

        with pytest.raises(
            CustomerReviewAlreadyExistsError,
        ):
            await create_customer_review(
                review=review,
                deduplication_key=deduplication_key,
            )

        count = await (
            CustomerReviewDocument.find(
                CustomerReviewDocument.business_id
                == business_id,
                CustomerReviewDocument.source
                == "google_maps",
                CustomerReviewDocument.deduplication_key
                == deduplication_key,
            ).count()
        )

        assert count == 1

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