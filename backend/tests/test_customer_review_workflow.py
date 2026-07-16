"""
Customer Review Complete Workflow Tests

Verifies the full workflow that resolves a stored customer review
by deduplication key and either creates, updates, or leaves the
review unchanged.
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
    store_normalized_customer_review,
)


def build_workflow_review(
    *,
    business_id,
    source_review_id: str | None,
    text: str = "الخدمة جيدة",
    rating: float | None = 4.0,
    information_quality: str = "medium",
    raw_data: dict | None = None,
) -> NormalizedCustomerReview:
    """Build one normalized review for workflow tests."""

    if raw_data is None:
        raw_data = {
            "source": "workflow_test",
        }

    return NormalizedCustomerReview(
        business_id=business_id,
        source="google_maps",
        source_review_id=source_review_id,
        text=text,
        language="ar",
        rating=rating,
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
        information_quality=(
            information_quality
        ),
        is_meaningful=True,
        is_emoji_only=False,
        raw_data=raw_data,
    )


@pytest.mark.asyncio
async def test_workflow_creates_updates_then_no_change():
    """Cover create, safe update, and no-change idempotent outcomes."""

    business_id = uuid4()

    source_review_id = (
        f"workflow-{uuid4().hex}"
    )

    stored_review_id = None

    try:
        await connect_to_mongo()

        # ====================================================
        # First: Create
        # ====================================================
        original = build_workflow_review(
            business_id=business_id,
            source_review_id=source_review_id,
        )

        first_result = (
            await store_normalized_customer_review(
                original
            )
        )

        stored_review_id = (
            first_result.review.id
        )

        assert stored_review_id is not None
        assert first_result.created is True
        assert first_result.updated is False

        assert (
            first_result.reason
            == "customer_review_created"
        )

        # ====================================================
        # Second: Safe Update With Changed Values
        # ====================================================
        updated_incoming = build_workflow_review(
            business_id=business_id,
            source_review_id=source_review_id,
            text=(
                "الخدمة ممتازة "
                "والقهوة رائعة"
            ),
            rating=5.0,
            information_quality="high",
            raw_data={
                "new_key": "new_value",
            },
        )

        second_result = (
            await store_normalized_customer_review(
                updated_incoming
            )
        )

        assert (
            second_result.review.id
            == stored_review_id
        )

        assert second_result.created is False
        assert second_result.updated is True

        assert (
            second_result.reason
            == "customer_review_updated"
        )

        assert (
            second_result.review.text
            == (
                "الخدمة ممتازة "
                "والقهوة رائعة"
            )
        )

        assert (
            second_result.review.rating
            == 5.0
        )

        assert (
            second_result.review
            .information_quality
            == "high"
        )

        # ====================================================
        # Third: Identical Observation → No Change
        # ====================================================
        third_result = (
            await store_normalized_customer_review(
                updated_incoming
            )
        )

        assert (
            third_result.review.id
            == stored_review_id
        )

        assert third_result.created is False
        assert third_result.updated is False

        assert (
            third_result.reason
            == "customer_review_already_exists"
        )

        # Only one document should exist.
        count = await (
            CustomerReviewDocument.find(
                CustomerReviewDocument.business_id
                == business_id,
                CustomerReviewDocument.source
                == "google_maps",
                CustomerReviewDocument.deduplication_key
                == (
                    second_result.review
                    .deduplication_key
                ),
            ).count()
        )

        assert count == 1

    finally:
        try:
            if stored_review_id is not None:
                persisted_review = (
                    await CustomerReviewDocument.get(
                        stored_review_id
                    )
                )

                if persisted_review is not None:
                    await persisted_review.delete()
        finally:
            await close_mongo()