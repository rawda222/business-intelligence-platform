"""
Customer Review Batch Storage Tests

Verifies batch result counting, continue-on-error behavior,
and strict fail-fast behavior for the customer review batch.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.normalized_social import (
    NormalizedCustomerReview,
)
from app.services import (
    customer_review_storage_service,
)
from app.services.customer_review_storage_service import (
    CustomerReviewAlreadyExistsError,
    CustomerReviewStorageResult,
    store_normalized_customer_reviews,
)


def build_batch_review(
    *,
    source_review_id: str,
) -> NormalizedCustomerReview:
    """Build one valid review for batch-policy tests."""

    return NormalizedCustomerReview(
        business_id=uuid4(),
        source="google_maps",
        source_review_id=source_review_id,
        text="Batch review test",
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
            "source": "batch_test",
        },
    )


@pytest.mark.asyncio
async def test_review_batch_counts_and_continues_after_failure(
    monkeypatch,
):
    """Count created, updated, unchanged, and failed reviews."""

    created_review = build_batch_review(
        source_review_id="created-review",
    )

    failed_review = build_batch_review(
        source_review_id="failed-review",
    )

    updated_review = build_batch_review(
        source_review_id="updated-review",
    )

    unchanged_review = build_batch_review(
        source_review_id="unchanged-review",
    )

    processed_ids: list[str] = []

    async def fake_store_normalized_customer_review(
        review,
    ):
        review_id = (
            review.source_review_id
            or ""
        )

        processed_ids.append(
            review_id
        )

        if review_id == "failed-review":
            raise CustomerReviewAlreadyExistsError(
                "Simulated duplicate"
            )

        stored_review = SimpleNamespace(
            source_review_id=review_id,
        )

        if review_id == "created-review":
            return CustomerReviewStorageResult(
                review=stored_review,
                created=True,
                updated=False,
                reason=(
                    "customer_review_created"
                ),
            )

        if review_id == "updated-review":
            return CustomerReviewStorageResult(
                review=stored_review,
                created=False,
                updated=True,
                reason=(
                    "customer_review_updated"
                ),
            )

        return CustomerReviewStorageResult(
            review=stored_review,
            created=False,
            updated=False,
            reason=(
                "customer_review_"
                "already_exists"
            ),
        )

    monkeypatch.setattr(
        customer_review_storage_service,
        "store_normalized_customer_review",
        fake_store_normalized_customer_review,
    )

    result = await store_normalized_customer_reviews(
        [
            created_review,
            failed_review,
            updated_review,
            unchanged_review,
        ],
        continue_on_error=True,
    )

    assert processed_ids == [
        "created-review",
        "failed-review",
        "updated-review",
        "unchanged-review",
    ]

    assert result.reviews_received == 4
    assert result.reviews_succeeded == 3

    assert result.reviews_created == 1
    assert result.reviews_updated == 1
    assert result.reviews_unchanged == 1

    assert len(result.results) == 3
    assert len(result.failures) == 1

    assert result.failures[0] == {
        "source": "google_maps",
        "source_review_id": (
            "failed-review"
        ),
        "error_type": (
            "CustomerReviewAlreadyExistsError"
        ),
        "error_message": (
            "Simulated duplicate"
        ),
    }

    failure_text = str(
        result.failures[0]
    )

    assert (
        "Batch review test"
        not in failure_text
    )

    assert "raw_data" not in failure_text


@pytest.mark.asyncio
async def test_review_batch_strict_mode_stops_at_failure(
    monkeypatch,
):
    """Raise the first error in strict batch mode."""

    first_review = build_batch_review(
        source_review_id="first-review",
    )

    failed_review = build_batch_review(
        source_review_id="strict-failure",
    )

    never_processed_review = build_batch_review(
        source_review_id="never-processed",
    )

    processed_ids: list[str] = []

    async def fake_store_normalized_customer_review(
        review,
    ):
        review_id = (
            review.source_review_id
            or ""
        )

        processed_ids.append(
            review_id
        )

        if review_id == "strict-failure":
            raise CustomerReviewAlreadyExistsError(
                "Strict simulated failure"
            )

        return CustomerReviewStorageResult(
            review=SimpleNamespace(
                source_review_id=review_id,
            ),
            created=True,
            updated=False,
            reason=(
                "customer_review_created"
            ),
        )

    monkeypatch.setattr(
        customer_review_storage_service,
        "store_normalized_customer_review",
        fake_store_normalized_customer_review,
    )

    with pytest.raises(
        CustomerReviewAlreadyExistsError,
        match="Strict simulated failure",
    ):
        await store_normalized_customer_reviews(
            [
                first_review,
                failed_review,
                never_processed_review,
            ],
            continue_on_error=False,
        )

    assert processed_ids == [
        "first-review",
        "strict-failure",
    ]

    assert (
        "never-processed"
        not in processed_ids
    )