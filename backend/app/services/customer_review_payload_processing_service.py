"""
Customer Review Payload Processing Service

Coordinates customer-review normalization with normalized-review
batch storage.

Current behavior:

- The raw business payload is normalized using
  normalize_and_assess_customer_reviews().
- The normalized reviews are persisted through the customer-review
  batch storage service.
- The source-quality assessment is returned to the caller for use
  by evidence, SWOT, and strategy layers.
- Storage failures follow the batch continue_on_error policy.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.preprocessing.customer_voice.review_normalizer import (
    normalize_and_assess_customer_reviews,
)
from app.schemas.normalized_social import (
    CustomerVoiceSource,
    NormalizedCustomerReview,
    SourceQualityAssessment,
)
from app.services.customer_review_storage_service import (
    CustomerReviewBatchStorageResult,
    store_normalized_customer_reviews,
)


# ============================================================
# Processing Result
# ============================================================
@dataclass(slots=True)
class CustomerReviewPayloadProcessingResult:
    """
    Result returned after processing one customer-review payload.

    source:
        Customer-voice source used for normalization and quality
        assessment.

    normalized_reviews:
        Valid reviews produced by the normalizer.

    assessment:
        Source-quality assessment computed from the normalized
        samples.

    storage:
        Batch storage summary for normalized reviews.
    """

    source: CustomerVoiceSource

    normalized_reviews: list[
        NormalizedCustomerReview
    ]

    assessment: SourceQualityAssessment

    storage: CustomerReviewBatchStorageResult

    @property
    def reviews_normalized(self) -> int:
        """Return the number of valid normalized reviews."""

        return len(
            self.normalized_reviews
        )

    @property
    def reviews_persisted(self) -> int:
        """
        Return the number of reviews successfully persisted.

        Successful outcomes include newly created, updated, and
        unchanged existing reviews because each successful result
        resolves to a persisted MongoDB document.
        """

        return (
            self.storage.reviews_succeeded
        )


# ============================================================
# Customer Review Payload Processing
# ============================================================
async def process_customer_review_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    source: CustomerVoiceSource = "google_maps",
    collected_at: datetime | None = None,
    continue_on_error: bool = True,
) -> CustomerReviewPayloadProcessingResult:
    """
    Normalize and store one complete customer-review payload.

    The normalizer already skips empty or invalid review records.
    Valid normalized reviews are persisted through the batch storage
    service.
    """

    normalized_reviews, assessment = (
        normalize_and_assess_customer_reviews(
            payload,
            business_id=business_id,
            collected_at=collected_at,
            source=source,
        )
    )

    storage_result = (
        await store_normalized_customer_reviews(
            normalized_reviews,
            continue_on_error=continue_on_error,
        )
    )

    return CustomerReviewPayloadProcessingResult(
        source=source,
        normalized_reviews=(
            normalized_reviews
        ),
        assessment=assessment,
        storage=storage_result,
    )