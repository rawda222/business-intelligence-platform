"""
Customer Review Lookup Tests

Verifies tenant-scoped customer-review lookup without depending on
storage or batch persistence services.
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
    find_existing_customer_review,
)


def build_lookup_review(
    *,
    business_id,
    source: str,
    source_review_id: str | None,
) -> NormalizedCustomerReview:
    """Build one normalized review for lookup tests."""

    return NormalizedCustomerReview(
        business_id=business_id,
        source=source,
        source_review_id=source_review_id,
        text="Parent lookup review",
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
            "source": "lookup_test",
        },
    )


@pytest.mark.asyncio
async def test_review_lookup_matches_only_exact_scope():
    """
    Match a review only inside the exact business and source scope.

    The lookup also requires an identical deduplication key.
    """

    business_a_id = uuid4()
    business_b_id = uuid4()

    matching_review = build_lookup_review(
        business_id=business_a_id,
        source="google_maps",
        source_review_id=(
            f"review-{uuid4().hex}"
        ),
    )

    deduplication_key = (
        build_customer_review_deduplication_key(
            matching_review
        )
    )

    stored_review = None

    try:
        await connect_to_mongo()

        stored_review = CustomerReviewDocument(
            business_id=matching_review.business_id,
            source=matching_review.source,
            source_review_id=(
                matching_review.source_review_id
            ),
            deduplication_key=deduplication_key,
            text=matching_review.text,
            language=matching_review.language,
            rating=matching_review.rating,
            published_at=(
                matching_review.published_at
            ),
            collected_at=(
                matching_review.collected_at
            ),
            information_quality=(
                matching_review.information_quality
            ),
            is_meaningful=(
                matching_review.is_meaningful
            ),
            is_emoji_only=(
                matching_review.is_emoji_only
            ),
            raw_data=dict(
                matching_review.raw_data
            ),
        )

        await stored_review.insert()

        # ====================================================
        # Exact Scope Must Match
        # ====================================================
        match = await find_existing_customer_review(
            review=matching_review,
            deduplication_key=deduplication_key,
        )

        assert match is not None
        assert match.id == stored_review.id

        # ====================================================
        # Different Business Must Not Match
        # ====================================================
        different_business_review = (
            matching_review.model_copy(
                update={
                    "business_id": business_b_id,
                },
            )
        )

        assert (
            await find_existing_customer_review(
                review=different_business_review,
                deduplication_key=deduplication_key,
            )
            is None
        )

        # ====================================================
        # Different Source Must Not Match
        # ====================================================
        different_source_review = (
            matching_review.model_copy(
                update={
                    "source": (
                        "facebook_reviews"
                    ),
                },
            )
        )

        assert (
            await find_existing_customer_review(
                review=different_source_review,
                deduplication_key=deduplication_key,
            )
            is None
        )

        # ====================================================
        # Different Deduplication Key Must Not Match
        # ====================================================
        assert (
            await find_existing_customer_review(
                review=matching_review,
                deduplication_key=(
                    "id:different-key"
                ),
            )
            is None
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
async def test_review_lookup_returns_none_when_missing():
    """Return None when no matching review exists."""

    try:
        await connect_to_mongo()

        review = build_lookup_review(
            business_id=uuid4(),
            source="google_maps",
            source_review_id=None,
        )

        deduplication_key = (
            build_customer_review_deduplication_key(
                review
            )
        )

        assert (
            await find_existing_customer_review(
                review=review,
                deduplication_key=deduplication_key,
            )
            is None
        )

    finally:
        await close_mongo()