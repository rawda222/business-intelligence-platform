"""
Customer Review Storage Service

Coordinates normalized customer-review identity and persistence.

Current stage:

- Build deterministic customer-review deduplication keys.
- Prefer external review IDs when the source platform provides them.
- Otherwise, build a stable SHA-256 identity from tenant scope,
  source, language, publication time, and text.

Storage functions are added after these identity rules are verified
independently from MongoDB.
"""

import hashlib
import json

from app.schemas.normalized_social import (
    NormalizedCustomerReview,
)
from app.services.post_metric_service import (
    ensure_utc,
)
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)


# ============================================================
# Deduplication Key
# ============================================================
def build_customer_review_deduplication_key(
    review: NormalizedCustomerReview,
) -> str:
    """
    Build a stable customer-review deduplication key.

    Preferred behavior:

    - Use the external source_review_id when available.
    - Long external IDs are digested with SHA-256 so the returned
      key always fits the MongoDB field length limit.

    Fallback behavior:

    - When no external review ID exists, generate a deterministic
      SHA-256 identity from:

      - business_id
      - source
      - language
      - published_at (normalized to UTC)
      - text

    Python hash() is intentionally not used because its output is
    not guaranteed to remain stable across processes.
    """

    source_review_id = (
        review.source_review_id.strip()
        if review.source_review_id is not None
        else ""
    )

    if source_review_id:
        readable_key = (
            f"id:{source_review_id}"
        )

        if len(readable_key) <= 128:
            return readable_key

        external_digest = hashlib.sha256(
            source_review_id.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            f"id-sha256:{external_digest}"
        )

    published_at = (
        ensure_utc(
            review.published_at
        ).isoformat()
        if review.published_at is not None
        else ""
    )

    canonical_identity = {
        "business_id": str(
            review.business_id
        ),
        "source": review.source,
        "language": review.language or "",
        "published_at": published_at,
        "text": review.text,
    }

    serialized_identity = json.dumps(
        canonical_identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    digest = hashlib.sha256(
        serialized_identity.encode(
            "utf-8"
        )
    ).hexdigest()

    return f"sha256:{digest}"

# ============================================================
# Existing Review Lookup
# ============================================================
async def find_existing_customer_review(
    *,
    review: NormalizedCustomerReview,
    deduplication_key: str,
) -> "CustomerReviewDocument | None":
    """
    Find an existing customer review inside the exact tenant scope.

    The lookup matches the fields protected by the unique MongoDB
    index:

    - business_id
    - source
    - deduplication_key

    Never search by external review_id alone. Two different
    businesses may collect reviews with identical external IDs from
    different sources.
    """

    return await CustomerReviewDocument.find_one(
        CustomerReviewDocument.business_id
        == review.business_id,
        CustomerReviewDocument.source
        == review.source,
        CustomerReviewDocument.deduplication_key
        == deduplication_key,
    )