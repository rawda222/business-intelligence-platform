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

from datetime import UTC, datetime

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

# ============================================================
# Storage Errors
# ============================================================
class CustomerReviewAlreadyExistsError(
    ValueError
):
    """
    Raised when a duplicate customer review is rejected.

    The unique MongoDB index on business_id + source +
    deduplication_key protects against inserting the same review
    twice. The service raises this error when Beanie or MongoDB
    rejects the insert with a DuplicateKeyError.
    """


# ============================================================
# Create Customer Review
# ============================================================
async def create_customer_review(
    *,
    review: NormalizedCustomerReview,
    deduplication_key: str,
) -> CustomerReviewDocument:
    """
    Create one MongoDB customer-review document.

    The deduplication key must already be resolved by the caller.

    The unique index on business_id + source + deduplication_key
    guarantees that duplicates cannot be inserted twice. When the
    database rejects the second insert, the service raises
    CustomerReviewAlreadyExistsError.
    """

    from pymongo.errors import DuplicateKeyError

    now = datetime.now(
        UTC,
    )

    normalized_published_at = (
        ensure_utc(
            review.published_at
        )
        if review.published_at is not None
        else None
    )

    normalized_source_review_id = (
        review.source_review_id.strip()
        if (
            review.source_review_id is not None
            and review.source_review_id.strip()
        )
        else None
    )

    stored_review = CustomerReviewDocument(
        business_id=review.business_id,
        source=review.source,
        source_review_id=(
            normalized_source_review_id
        ),
        deduplication_key=deduplication_key,
        text=review.text,
        language=review.language,
        rating=review.rating,
        published_at=normalized_published_at,
        collected_at=ensure_utc(
            review.collected_at
        ),
        information_quality=(
            review.information_quality
        ),
        is_meaningful=review.is_meaningful,
        is_emoji_only=review.is_emoji_only,
        raw_data=dict(
            review.raw_data
        ),
        created_at=now,
        updated_at=now,
    )

    try:
        await stored_review.insert()
    except DuplicateKeyError as error:
        raise CustomerReviewAlreadyExistsError(
            "Customer review already exists "
            "inside this tenant, source, and "
            "deduplication key."
        ) from error

    return stored_review

# ============================================================
# Safe Customer Review Update
# ============================================================
async def update_customer_review_safely(
    *,
    stored_review: CustomerReviewDocument,
    incoming_review: NormalizedCustomerReview,
) -> bool:
    """
    Safely update mutable customer-review fields.

    Update policy:

    - Non-None scalar values may update stored values.
    - None does not erase useful stored information.
    - Zero and empty strings from incoming data are treated as
      missing information and do not overwrite stored fields.
    - raw_data values are merged without removing keys.
    - Identity fields are never modified:
      - business_id
      - source
      - source_review_id
      - deduplication_key

    Returns:
        True when at least one persisted field changed.
        False when the incoming observation is identical.
    """

    changed = False

    # ========================================================
    # Review Text
    # ========================================================
    incoming_text = incoming_review.text

    if (
        incoming_text
        and stored_review.text != incoming_text
    ):
        stored_review.text = incoming_text

        changed = True

    # ========================================================
    # Language
    # ========================================================
    incoming_language = incoming_review.language

    if (
        incoming_language
        and stored_review.language
        != incoming_language
    ):
        stored_review.language = (
            incoming_language
        )

        changed = True

    # ========================================================
    # Rating
    # ========================================================
    incoming_rating = incoming_review.rating

    if (
        incoming_rating is not None
        and stored_review.rating
        != incoming_rating
    ):
        stored_review.rating = incoming_rating

        changed = True

    # ========================================================
    # Publication Time
    # ========================================================
    incoming_published_at = (
        ensure_utc(
            incoming_review.published_at
        )
        if incoming_review.published_at
        is not None
        else None
    )

    stored_published_at = (
        ensure_utc(
            stored_review.published_at
        )
        if stored_review.published_at
        is not None
        else None
    )

    if (
        incoming_published_at is not None
        and stored_published_at
        != incoming_published_at
    ):
        stored_review.published_at = (
            incoming_published_at
        )

        changed = True

    # ========================================================
    # Information Quality
    # ========================================================
    if (
        stored_review.information_quality
        != incoming_review.information_quality
    ):
        stored_review.information_quality = (
            incoming_review.information_quality
        )

        changed = True

    # ========================================================
    # Meaningfulness
    # ========================================================
    if (
        stored_review.is_meaningful
        != incoming_review.is_meaningful
    ):
        stored_review.is_meaningful = (
            incoming_review.is_meaningful
        )

        changed = True

    if (
        stored_review.is_emoji_only
        != incoming_review.is_emoji_only
    ):
        stored_review.is_emoji_only = (
            incoming_review.is_emoji_only
        )

        changed = True

    # ========================================================
    # Minimized Raw Data Merge
    # ========================================================
    stored_raw_data = dict(
        stored_review.raw_data
        or {}
    )

    merged_raw_data = dict(
        stored_raw_data
    )

    for key, value in (
        incoming_review.raw_data.items()
    ):
        if value is None:
            continue

        merged_raw_data[key] = value

    if merged_raw_data != stored_raw_data:
        stored_review.raw_data = (
            merged_raw_data
        )

        changed = True

    # ========================================================
    # Persist Only When Necessary
    # ========================================================
    if not changed:
        return False

    stored_review.updated_at = datetime.now(
        UTC,
    )

    stored_review.collected_at = ensure_utc(
        incoming_review.collected_at
    )

    await stored_review.save()

    return True
# ============================================================
# Storage Result and Complete Workflow
# ============================================================
from dataclasses import dataclass


@dataclass(slots=True)
class CustomerReviewStorageResult:
    """
    Result returned after storing one normalized customer review.

    review:
        The persisted MongoDB customer-review document.

    created:
        True when a new review document was inserted.

    updated:
        True when an existing review was safely updated.

    reason:
        Machine-readable storage outcome.
    """

    review: CustomerReviewDocument

    created: bool

    updated: bool

    reason: str


async def store_normalized_customer_review(
    review: NormalizedCustomerReview,
) -> CustomerReviewStorageResult:
    """
    Store one normalized customer review idempotently.

    Workflow:

    1. Build the deterministic deduplication key.
    2. Look up an existing review inside the same tenant and source.
    3. Safely update the existing review when mutable fields change.
    4. Return the existing review when nothing changed.
    5. Create a new review when no matching identity exists.
    """

    deduplication_key = (
        build_customer_review_deduplication_key(
            review
        )
    )

    existing_review = (
        await find_existing_customer_review(
            review=review,
            deduplication_key=deduplication_key,
        )
    )

    if existing_review is not None:
        updated = await update_customer_review_safely(
            stored_review=existing_review,
            incoming_review=review,
        )

        if not updated:
            return CustomerReviewStorageResult(
                review=existing_review,
                created=False,
                updated=False,
                reason=(
                    "customer_review_"
                    "already_exists"
                ),
            )

        if existing_review.id is None:
            raise RuntimeError(
                "Updated customer review has no "
                "persisted document ID."
            )

        refreshed_review = (
            await CustomerReviewDocument.get(
                existing_review.id
            )
        )

        if refreshed_review is None:
            raise RuntimeError(
                "Updated customer review could "
                "not be reloaded."
            )

        return CustomerReviewStorageResult(
            review=refreshed_review,
            created=False,
            updated=True,
            reason=(
                "customer_review_updated"
            ),
        )

    created_review = (
        await create_customer_review(
            review=review,
            deduplication_key=deduplication_key,
        )
    )

    return CustomerReviewStorageResult(
        review=created_review,
        created=True,
        updated=False,
        reason=(
            "customer_review_created"
        ),
    )