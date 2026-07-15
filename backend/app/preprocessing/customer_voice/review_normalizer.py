"""
Customer Review Normalizer

Converts business customer-review payloads into normalized,
platform-independent customer-voice contracts.

The currently supported business payload includes:

- reviews.summary
- reviews.raw_samples
    - text
    - rating
    - source

Some review texts may be stored as a string representation of a
language dictionary, for example:

    "{'ar': 'المكان جميل والخدمة ممتازة'}"

The normalizer parses this representation safely using
ast.literal_eval. It never uses eval().
"""

import ast
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.preprocessing.social.common import (
    get_first_present_value,
    infer_information_quality,
    is_emoji_only_text,
    normalize_external_identifier,
    normalize_text,
    parse_datetime_utc,
)
from app.schemas.normalized_social import (
    ConfidenceLevel,
    CustomerVoiceSource,
    NormalizedCustomerReview,
    SourceQualityAssessment,
    SourceRole,
)


# ============================================================
# Supported Source Mapping
# ============================================================
SOURCE_MAPPING: dict[str, CustomerVoiceSource] = {
    "google_maps": "google_maps",
    "google maps": "google_maps",
    "googlemaps": "google_maps",
    "google": "google_maps",
    "facebook_comments": "facebook_comments",
    "facebook comments": "facebook_comments",
    "facebook_reviews": "facebook_reviews",
    "facebook reviews": "facebook_reviews",
    "facebook_recommendations": "facebook_reviews",
    "facebook recommendations": "facebook_reviews",
    "instagram_comments": "instagram_comments",
    "instagram comments": "instagram_comments",
    "linkedin_comments": "linkedin_comments",
    "linkedin comments": "linkedin_comments",
    "tiktok_comments": "tiktok_comments",
    "tiktok comments": "tiktok_comments",
    "website_reviews": "website_reviews",
    "website reviews": "website_reviews",
}


# ============================================================
# Parsed Review Text
# ============================================================
@dataclass(frozen=True, slots=True)
class ParsedReviewText:
    """
    Parsed customer-review content.

    text:
        Clean customer review text.

    language:
        Optional normalized language code extracted from explicit
        metadata or a serialized language dictionary.
    """

    text: str

    language: str | None


# ============================================================
# Source Normalization
# ============================================================
def normalize_review_source(
    value: object,
) -> CustomerVoiceSource:
    """
    Normalize an external review-source name.

    Unknown or missing sources use the shared "other" value.
    """

    normalized = normalize_text(value)

    if normalized is None:
        return "other"

    key = (
        normalized
        .casefold()
        .replace("-", "_")
    )

    return SOURCE_MAPPING.get(
        key,
        "other",
    )


# ============================================================
# Rating Parsing
# ============================================================
def parse_review_rating(
    value: object,
) -> float | None:
    """
    Parse a customer-review rating between zero and five.

    Examples:
        5         -> 5.0
        "4"       -> 4.0
        "4.5"     -> 4.5
        None      -> None
        True      -> None
        -1        -> None
        6         -> None
        "invalid" -> None
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None

    if rating < 0 or rating > 5:
        return None

    return rating


# ============================================================
# Language Normalization
# ============================================================
def normalize_language_code(
    value: object,
) -> str | None:
    """
    Normalize a short language code.

    Examples:
        "AR"    -> "ar"
        "en-US" -> "en-us"

    Empty or excessively long values are ignored.
    """

    normalized = normalize_text(value)

    if normalized is None:
        return None

    normalized = normalized.lower()

    if len(normalized) < 2 or len(normalized) > 20:
        return None

    return normalized


# ============================================================
# Nested Review-Text Parsing
# ============================================================
def parse_mapping_text(
    value: object,
) -> ParsedReviewText | None:
    """
    Extract review text from a dictionary-like object.

    The first non-empty language-text pair is used while preserving
    the original dictionary insertion order.
    """

    if not isinstance(value, dict):
        return None

    for language_value, text_value in value.items():
        text = normalize_text(text_value)

        if text is None:
            continue

        return ParsedReviewText(
            text=text,
            language=normalize_language_code(
                language_value
            ),
        )

    return None


def try_parse_serialized_mapping(
    value: str,
) -> ParsedReviewText | None:
    """
    Parse text that may represent a language dictionary.

    Safe parsers are attempted in this order:

    1. json.loads for valid JSON:
       {"ar": "النص"}

    2. ast.literal_eval for Python-literal style:
       {'ar': 'النص'}

    Parsing failures return None and the value is later treated as
    ordinary plain text.
    """

    stripped = value.strip()

    if not (
        stripped.startswith("{")
        and stripped.endswith("}")
    ):
        return None

    try:
        parsed_json = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        parsed_json = None

    parsed_review = parse_mapping_text(
        parsed_json
    )

    if parsed_review is not None:
        return parsed_review

    try:
        parsed_literal = ast.literal_eval(
            stripped
        )
    except (
        SyntaxError,
        ValueError,
        TypeError,
        MemoryError,
        RecursionError,
    ):
        return None

    return parse_mapping_text(
        parsed_literal
    )


def parse_review_text(
    value: object,
    *,
    explicit_language: object = None,
) -> ParsedReviewText | None:
    """
    Normalize a review-text value.

    Supported inputs:
    - Plain string
    - JSON dictionary string
    - Python-literal dictionary string
    - Actual dictionary

    Explicit language metadata has priority over language metadata
    embedded in the text representation.
    """

    explicit_language_code = normalize_language_code(
        explicit_language
    )

    direct_mapping = parse_mapping_text(
        value
    )

    if direct_mapping is not None:
        return ParsedReviewText(
            text=direct_mapping.text,
            language=(
                explicit_language_code
                or direct_mapping.language
            ),
        )

    plain_text = normalize_text(value)

    if plain_text is None:
        return None

    parsed_mapping = try_parse_serialized_mapping(
        plain_text
    )

    if parsed_mapping is not None:
        return ParsedReviewText(
            text=parsed_mapping.text,
            language=(
                explicit_language_code
                or parsed_mapping.language
            ),
        )

    return ParsedReviewText(
        text=plain_text,
        language=explicit_language_code,
    )


# ============================================================
# Meaningfulness Policy
# ============================================================
def is_meaningful_customer_review(
    text: str,
) -> bool:
    """
    Determine whether a review contains useful customer evidence.

    A review is meaningful when:
    - It is not emoji-only or punctuation-only.
    - Its structural information quality is medium or high.

    A one-word reaction may still be useful as a lightweight
    reaction signal, but it is not strong customer-experience
    evidence.
    """

    if is_emoji_only_text(text):
        return False

    quality = infer_information_quality(
        text
    )

    return quality in {
        "medium",
        "high",
    }


# ============================================================
# Minimized Raw Payload
# ============================================================
def build_minimized_review_raw_data(
    raw_review: dict[str, Any],
) -> dict[str, object]:
    """
    Keep minimal customer-review traceability data.

    The original serialized text is not duplicated because normalized
    text and language are stored explicitly.
    """

    source_review_id = get_first_present_value(
        raw_review,
        "id",
        "review_id",
    )

    allowed_fields = {
        "source": raw_review.get("source"),
        "source_review_id": source_review_id,
    }

    return {
        key: value
        for key, value in allowed_fields.items()
        if value is not None
    }


# ============================================================
# Single Review Normalization
# ============================================================
def normalize_customer_review(
    raw_review: dict[str, Any],
    *,
    business_id: UUID,
    collected_at: datetime,
    default_source: CustomerVoiceSource = "other",
) -> NormalizedCustomerReview | None:
    """
    Normalize one customer review.

    Empty or unusable text records are skipped.
    """

    parsed_text = parse_review_text(
        raw_review.get("text"),
        explicit_language=raw_review.get(
            "language"
        ),
    )

    if parsed_text is None:
        return None

    normalized_collected_at = parse_datetime_utc(
        collected_at
    )

    if normalized_collected_at is None:
        raise ValueError(
            "collected_at must be a valid datetime."
        )

    source = normalize_review_source(
        raw_review.get("source")
    )

    if source == "other":
        source = default_source

    published_at_value = get_first_present_value(
        raw_review,
        "published_at",
        "created_at",
        "date",
    )

    source_review_id_value = get_first_present_value(
        raw_review,
        "id",
        "review_id",
    )

    information_quality = infer_information_quality(
        parsed_text.text
    )

    emoji_only = is_emoji_only_text(
        parsed_text.text
    )

    meaningful = is_meaningful_customer_review(
        parsed_text.text
    )

    return NormalizedCustomerReview(
        business_id=business_id,
        source=source,
        source_review_id=(
            normalize_external_identifier(
                source_review_id_value
            )
        ),
        text=parsed_text.text,
        language=parsed_text.language,
        rating=parse_review_rating(
            raw_review.get("rating")
        ),
        published_at=parse_datetime_utc(
            published_at_value
        ),
        collected_at=normalized_collected_at,
        information_quality=information_quality,
        is_meaningful=meaningful,
        is_emoji_only=emoji_only,
        raw_data=build_minimized_review_raw_data(
            raw_review
        ),
    )


# ============================================================
# Volume-Style Payload Extraction
# ============================================================
def extract_review_samples(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract review samples from a business-intelligence payload.

    Expected structure:

        payload["reviews"]["raw_samples"]

    Invalid sample records are ignored.
    """

    reviews_section = payload.get(
        "reviews"
    )

    if not isinstance(reviews_section, dict):
        return []

    raw_samples = reviews_section.get(
        "raw_samples"
    )

    if not isinstance(raw_samples, list):
        return []

    return [
        sample
        for sample in raw_samples
        if isinstance(sample, dict)
    ]


def extract_declared_total_reviews(
    payload: dict[str, Any],
) -> int | None:
    """
    Read the declared total review count from reviews.summary.

    The declared total may exceed the number of raw samples available
    in the file. Quality calculation uses the normalized samples
    actually available for analysis.
    """

    reviews_section = payload.get(
        "reviews"
    )

    if not isinstance(reviews_section, dict):
        return None

    summary = reviews_section.get(
        "summary"
    )

    if not isinstance(summary, dict):
        return None

    value = summary.get(
        "total_reviews"
    )

    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return None

    return parsed


# ============================================================
# Complete Payload Normalization
# ============================================================
def normalize_customer_review_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    collected_at: datetime | None = None,
    default_source: CustomerVoiceSource = "google_maps",
) -> list[NormalizedCustomerReview]:
    """
    Normalize all usable customer reviews in a business payload.

    When collected_at is missing, current UTC time is used.

    One malformed review does not discard the complete review batch.
    """

    normalized_collected_at = parse_datetime_utc(
        collected_at
    )

    if normalized_collected_at is None:
        normalized_collected_at = datetime.now(
            UTC
        )

    raw_samples = extract_review_samples(
        payload
    )

    normalized_reviews: list[
        NormalizedCustomerReview
    ] = []

    for raw_review in raw_samples:
        normalized = normalize_customer_review(
            raw_review,
            business_id=business_id,
            collected_at=normalized_collected_at,
            default_source=default_source,
        )

        if normalized is not None:
            normalized_reviews.append(
                normalized
            )

    return normalized_reviews


# ============================================================
# Source-Quality Policy
# ============================================================
def determine_source_role(
    *,
    source: CustomerVoiceSource,
    available: bool,
    sample_size: int,
    meaningful_text_ratio: float,
) -> SourceRole:
    """
    Determine one customer-voice source's analytical role.

    Current policy:

    Google Maps:
    - Primary when at least five samples exist and at least half
      contain meaningful customer evidence.
    - Supporting when samples exist but do not meet the primary
      threshold.
    - Fallback when no usable sample is available.

    Social comments:
    - Supporting when useful samples exist.
    - Fallback when unavailable or too weak.

    Social posts are not evaluated here because they belong to the
    separate social-content trend pipeline.
    """

    if source == "google_maps":
        if (
            available
            and sample_size >= 5
            and meaningful_text_ratio >= 0.5
        ):
            return "primary_customer_voice"

        if available:
            return "supporting_customer_voice"

        return "fallback_customer_voice"

    if (
        available
        and sample_size > 0
        and meaningful_text_ratio >= 0.3
    ):
        return "supporting_customer_voice"

    return "fallback_customer_voice"


def determine_confidence(
    *,
    available: bool,
    sample_size: int,
    meaningful_text_ratio: float,
) -> ConfidenceLevel:
    """
    Determine confidence from available normalized evidence.

    Current policy:
    - insufficient: no normalized samples
    - high: at least ten samples and at least 70% meaningful
    - medium: at least five samples and at least 50% meaningful
    - low: any other available sample set
    """

    if not available or sample_size == 0:
        return "insufficient"

    if (
        sample_size >= 10
        and meaningful_text_ratio >= 0.7
    ):
        return "high"

    if (
        sample_size >= 5
        and meaningful_text_ratio >= 0.5
    ):
        return "medium"

    return "low"


def assess_review_source_quality(
    reviews: list[NormalizedCustomerReview],
    *,
    source: CustomerVoiceSource,
    declared_total_reviews: int | None = None,
) -> SourceQualityAssessment:
    """
    Calculate source quality from normalized reviews.

    sample_size is based on review texts actually available to the
    analysis pipeline, not only an aggregate count reported by the
    external platform.
    """

    source_reviews = [
        review
        for review in reviews
        if review.source == source
    ]

    sample_size = len(
        source_reviews
    )

    meaningful_sample_count = sum(
        1
        for review in source_reviews
        if review.is_meaningful
    )

    emoji_only_count = sum(
        1
        for review in source_reviews
        if review.is_emoji_only
    )

    meaningful_text_ratio = (
        meaningful_sample_count / sample_size
        if sample_size > 0
        else 0.0
    )

    emoji_only_ratio = (
        emoji_only_count / sample_size
        if sample_size > 0
        else 0.0
    )

    available = sample_size > 0

    source_role = determine_source_role(
        source=source,
        available=available,
        sample_size=sample_size,
        meaningful_text_ratio=meaningful_text_ratio,
    )

    confidence = determine_confidence(
        available=available,
        sample_size=sample_size,
        meaningful_text_ratio=meaningful_text_ratio,
    )

    has_ratings = any(
        review.rating is not None
        for review in source_reviews
    )

    has_publication_dates = any(
        review.published_at is not None
        for review in source_reviews
    )

    notes: list[str] = []

    if declared_total_reviews is not None:
        notes.append(
            "Declared platform total reviews: "
            f"{declared_total_reviews}"
        )

        if declared_total_reviews != sample_size:
            notes.append(
                "Quality assessment uses the available "
                f"normalized sample size: {sample_size}"
            )

    if emoji_only_count > 0:
        notes.append(
            f"Emoji-only samples: {emoji_only_count}"
        )

    if available and not has_publication_dates:
        notes.append(
            "Available review samples do not include "
            "publication dates."
        )

    return SourceQualityAssessment(
        source=source,
        source_role=source_role,
        available=available,
        sample_size=sample_size,
        meaningful_sample_count=meaningful_sample_count,
        emoji_only_count=emoji_only_count,
        meaningful_text_ratio=meaningful_text_ratio,
        emoji_only_ratio=emoji_only_ratio,
        has_ratings=has_ratings,
        has_publication_dates=has_publication_dates,
        confidence=confidence,
        notes=notes,
    )


# ============================================================
# Combined Normalization and Assessment
# ============================================================
def normalize_and_assess_customer_reviews(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    collected_at: datetime | None = None,
    source: CustomerVoiceSource = "google_maps",
) -> tuple[
    list[NormalizedCustomerReview],
    SourceQualityAssessment,
]:
    """
    Normalize customer reviews and calculate source quality.

    Returns:
        A tuple containing:
        - normalized customer reviews
        - calculated source-quality assessment
    """

    reviews = normalize_customer_review_payload(
        payload,
        business_id=business_id,
        collected_at=collected_at,
        default_source=source,
    )

    declared_total_reviews = (
        extract_declared_total_reviews(
            payload
        )
    )

    assessment = assess_review_source_quality(
        reviews,
        source=source,
        declared_total_reviews=declared_total_reviews,
    )

    return reviews, assessment