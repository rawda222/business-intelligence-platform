"""
Cross-Source Customer Voice Service

Converts normalized customer-review and social-comment documents
into the unified review contract consumed by the existing Theme
Extractor.

Supported customer-voice sources:

- Google Maps reviews.
- Facebook reviews.
- Facebook comments.
- Instagram comments.

The service:

- Preserves tenant isolation.
- Reuses the existing review normalization and sentiment hint logic.
- Produces stable, source-aware evidence references.
- Deduplicates comments stored in more than one collection.
- Excludes emoji-only and explicitly non-meaningful records.
- Does not treat brand-owned posts as customer sentiment.
- Does not query MongoDB or call an LLM.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.preprocessing.normalize.reviews import (
    normalize_review,
)


CustomerVoicePlatform = Literal[
    "google_maps",
    "facebook",
    "instagram",
]

CustomerVoiceEntity = Literal[
    "review",
    "comment",
]


_ALLOWED_REVIEW_SOURCES = {
    "google_maps",
    "facebook_comments",
    "facebook_reviews",
    "instagram_comments",
}

_ALLOWED_COMMENT_PLATFORMS = {
    "facebook",
    "instagram",
}


@dataclass(frozen=True, slots=True)
class CrossSourceCustomerVoiceResult:
    """Normalized customer voice ready for theme extraction."""

    business_id: UUID

    business_name: str

    business_type: str

    business_reviews: tuple[dict[str, Any], ...]

    records_received: int

    records_included: int

    records_excluded: int

    duplicate_records: int

    records_by_source: tuple[
        tuple[str, int],
        ...
    ]

    warnings: tuple[str, ...]

    def as_theme_extractor_input(
        self,
    ) -> dict[str, Any]:
        """Return the envelope consumed by extract_themes()."""

        return {
            "business_name": self.business_name,
            "business_type": self.business_type,
            "business_reviews": [
                dict(record)
                for record in self.business_reviews
            ],
            "competitors": [],
        }


def _get_value(
    value: Any,
    field_name: str,
    default: Any = None,
) -> Any:
    """Read one field from a mapping or object."""

    if isinstance(value, dict):
        return value.get(
            field_name,
            default,
        )

    return getattr(
        value,
        field_name,
        default,
    )


def _clean_optional_text(
    value: Any,
) -> str | None:
    """Return stripped text or None."""

    if not isinstance(value, str):
        return None

    cleaned = value.strip()

    return cleaned or None


def _clean_required_text(
    value: Any,
    *,
    default: str,
) -> str:
    """Return stripped text with a fallback."""

    cleaned = _clean_optional_text(
        value
    )

    return cleaned or default


def _document_business_id(
    value: Any,
) -> UUID | None:
    """Read a document business identifier."""

    raw_business_id = _get_value(
        value,
        "business_id",
    )

    if isinstance(
        raw_business_id,
        UUID,
    ):
        return raw_business_id

    if isinstance(
        raw_business_id,
        str,
    ):
        try:
            return UUID(
                raw_business_id
            )
        except ValueError:
            return None

    return None


def _ensure_business_scope(
    *,
    value: Any,
    business_id: UUID,
) -> None:
    """Reject records from another tenant or invalid scope."""

    record_business_id = (
        _document_business_id(
            value
        )
    )

    if record_business_id != business_id:
        raise ValueError(
            "Customer-voice record business_id "
            "does not match the requested business_id."
        )


def _safe_identifier(
    value: Any,
) -> str | None:
    """Normalize one external identifier."""

    if value is None:
        return None

    cleaned = str(
        value
    ).strip()

    return cleaned or None


def _review_source_parts(
    source: str,
) -> tuple[
    CustomerVoicePlatform,
    CustomerVoiceEntity,
]:
    """Map a stored review source to evidence reference parts."""

    if source == "google_maps":
        return (
            "google_maps",
            "review",
        )

    if source == "facebook_reviews":
        return (
            "facebook",
            "review",
        )

    if source == "facebook_comments":
        return (
            "facebook",
            "comment",
        )

    if source == "instagram_comments":
        return (
            "instagram",
            "comment",
        )

    raise ValueError(
        f"Unsupported customer-review source: {source}"
    )


def _evidence_reference(
    *,
    platform: CustomerVoicePlatform,
    entity: CustomerVoiceEntity,
    external_id: str | None,
    deduplication_key: str,
) -> str:
    """Build a stable source-aware evidence reference."""

    identity = (
        external_id
        or deduplication_key
    )

    return (
        f"{platform}:"
        f"{entity}:"
        f"{identity}"
    )


def _quality_report() -> dict[str, list[Any]]:
    """Build the mutable quality contract used by normalize_review."""

    return {
        "missing_fields": [],
        "synthetic_items": [],
        "manual_review_needed": [],
        "duplicates_found": [],
    }


def _normalize_customer_voice_record(
    *,
    raw_text: str,
    rating: Any,
    source: str,
    evidence_reference: str,
    business_name: str,
    index: int,
) -> dict[str, Any]:
    """
    Normalize one customer-voice record using the existing pipeline.

    The generated review ID is replaced with the stable evidence
    reference so Theme Extractor mentions remain source-traceable.
    """

    normalized = normalize_review(
        raw_review={
            "text": raw_text,
            "rating": rating,
        },
        entity_name=business_name,
        entity_type="target_business",
        index=index,
        source=source,
        quality_report=_quality_report(),
    )

    normalized["review_id"] = (
        evidence_reference
    )

    normalized["evidence_reference"] = (
        evidence_reference
    )

    normalized["source"] = source

    return normalized


def _customer_review_candidate(
    *,
    document: Any,
    business_id: UUID,
    business_name: str,
    index: int,
) -> tuple[
    str,
    dict[str, Any] | None,
    str | None,
]:
    """
    Convert one CustomerReviewDocument-like value.

    Returns:
        deduplication identity,
        normalized review or None,
        exclusion reason or None.
    """

    _ensure_business_scope(
        value=document,
        business_id=business_id,
    )

    source = _clean_required_text(
        _get_value(
            document,
            "source",
        ),
        default="",
    )

    if source not in _ALLOWED_REVIEW_SOURCES:
        return (
            "",
            None,
            "unsupported_review_source",
        )

    platform, entity = (
        _review_source_parts(
            source
        )
    )

    text = _clean_optional_text(
        _get_value(
            document,
            "text",
        )
    )

    if not text:
        return (
            "",
            None,
            "empty_review_text",
        )

    if bool(
        _get_value(
            document,
            "is_emoji_only",
            False,
        )
    ):
        return (
            "",
            None,
            "emoji_only_review",
        )

    is_meaningful = _get_value(
        document,
        "is_meaningful",
        True,
    )

    if is_meaningful is False:
        return (
            "",
            None,
            "non_meaningful_review",
        )

    external_id = _safe_identifier(
        _get_value(
            document,
            "source_review_id",
        )
    )

    deduplication_key = (
        _clean_required_text(
            _get_value(
                document,
                "deduplication_key",
            ),
            default="missing",
        )
    )

    reference = _evidence_reference(
        platform=platform,
        entity=entity,
        external_id=external_id,
        deduplication_key=(
            deduplication_key
        ),
    )

    normalized = (
        _normalize_customer_voice_record(
            raw_text=text,
            rating=_get_value(
                document,
                "rating",
            ),
            source=source,
            evidence_reference=reference,
            business_name=business_name,
            index=index,
        )
    )

    return (
        reference,
        normalized,
        None,
    )


def _social_comment_candidate(
    *,
    document: Any,
    business_id: UUID,
    business_name: str,
    index: int,
) -> tuple[
    str,
    dict[str, Any] | None,
    str | None,
]:
    """
    Convert one SocialCommentDocument-like value.

    Facebook and Instagram comments become supporting customer
    voice. Brand-owned posts are intentionally not handled here.
    """

    _ensure_business_scope(
        value=document,
        business_id=business_id,
    )

    platform = _clean_required_text(
        _get_value(
            document,
            "platform",
        ),
        default="",
    )

    if platform not in _ALLOWED_COMMENT_PLATFORMS:
        return (
            "",
            None,
            "unsupported_comment_platform",
        )

    text = _clean_optional_text(
        _get_value(
            document,
            "text",
        )
    )

    if not text:
        return (
            "",
            None,
            "empty_comment_text",
        )

    if bool(
        _get_value(
            document,
            "is_emoji_only",
            False,
        )
    ):
        return (
            "",
            None,
            "emoji_only_comment",
        )

    information_quality = (
        _clean_required_text(
            _get_value(
                document,
                "information_quality",
            ),
            default="low",
        )
    )

    if information_quality == "low":
        return (
            "",
            None,
            "low_quality_comment",
        )

    external_id = _safe_identifier(
        _get_value(
            document,
            "platform_comment_id",
        )
    )

    deduplication_key = (
        _clean_required_text(
            _get_value(
                document,
                "deduplication_key",
            ),
            default="missing",
        )
    )

    typed_platform: CustomerVoicePlatform

    if platform == "facebook":
        typed_platform = "facebook"
        source = "facebook_comments"
    else:
        typed_platform = "instagram"
        source = "instagram_comments"

    reference = _evidence_reference(
        platform=typed_platform,
        entity="comment",
        external_id=external_id,
        deduplication_key=(
            deduplication_key
        ),
    )

    normalized = (
        _normalize_customer_voice_record(
            raw_text=text,
            rating=None,
            source=source,
            evidence_reference=reference,
            business_name=business_name,
            index=index,
        )
    )

    return (
        reference,
        normalized,
        None,
    )


def build_cross_source_customer_voice(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    customer_reviews: Iterable[Any] = (),
    social_comments: Iterable[Any] = (),
) -> CrossSourceCustomerVoiceResult:
    """
    Build deduplicated customer voice for Theme Extractor.

    CustomerReviewDocument records are processed first. When the
    same Facebook or Instagram comment also appears in
    SocialCommentDocument, the customer-review representation wins.
    """

    normalized_business_name = (
        _clean_required_text(
            business_name,
            default="Unknown",
        )
    )

    normalized_business_type = (
        _clean_required_text(
            business_type,
            default="unknown",
        )
    )

    review_documents = list(
        customer_reviews
    )

    comment_documents = list(
        social_comments
    )

    records_received = (
        len(review_documents)
        + len(comment_documents)
    )

    included: list[
        dict[str, Any]
    ] = []

    seen_identities: set[str] = set()

    duplicate_records = 0

    excluded_records = 0

    warnings: list[str] = []

    counts_by_source: dict[str, int] = {}

    current_index = 0

    for document in review_documents:
        current_index += 1

        (
            identity,
            normalized,
            exclusion_reason,
        ) = _customer_review_candidate(
            document=document,
            business_id=business_id,
            business_name=(
                normalized_business_name
            ),
            index=current_index,
        )

        if exclusion_reason is not None:
            excluded_records += 1
            warnings.append(
                exclusion_reason
            )
            continue

        if identity in seen_identities:
            duplicate_records += 1
            continue

        if normalized is None:
            excluded_records += 1
            continue

        seen_identities.add(
            identity
        )

        included.append(
            normalized
        )

        source = str(
            normalized["source"]
        )

        counts_by_source[source] = (
            counts_by_source.get(
                source,
                0,
            )
            + 1
        )

    for document in comment_documents:
        current_index += 1

        (
            identity,
            normalized,
            exclusion_reason,
        ) = _social_comment_candidate(
            document=document,
            business_id=business_id,
            business_name=(
                normalized_business_name
            ),
            index=current_index,
        )

        if exclusion_reason is not None:
            excluded_records += 1
            warnings.append(
                exclusion_reason
            )
            continue

        if identity in seen_identities:
            duplicate_records += 1
            continue

        if normalized is None:
            excluded_records += 1
            continue

        seen_identities.add(
            identity
        )

        included.append(
            normalized
        )

        source = str(
            normalized["source"]
        )

        counts_by_source[source] = (
            counts_by_source.get(
                source,
                0,
            )
            + 1
        )

    return CrossSourceCustomerVoiceResult(
        business_id=business_id,
        business_name=(
            normalized_business_name
        ),
        business_type=(
            normalized_business_type
        ),
        business_reviews=tuple(
            included
        ),
        records_received=(
            records_received
        ),
        records_included=len(
            included
        ),
        records_excluded=(
            excluded_records
        ),
        duplicate_records=(
            duplicate_records
        ),
        records_by_source=tuple(
            counts_by_source.items()
        ),
        warnings=tuple(
            dict.fromkeys(
                warnings
            )
        ),
    )

