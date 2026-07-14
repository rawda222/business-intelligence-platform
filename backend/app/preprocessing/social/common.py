"""
Shared Social Normalization Utilities

Contains platform-independent helpers used by social-media
normalizers.

These helpers perform structural normalization only. They do not
perform sentiment analysis, topic modeling, or strategic inference.
"""

import re
from datetime import UTC, datetime
from typing import Any

from app.schemas.normalized_social import InformationQuality


# ============================================================
# Date-Time Parsing
# ============================================================
def parse_datetime_utc(
    value: object,
) -> datetime | None:
    """
    Parse a datetime value and normalize it to UTC.

    Supported inputs:
    - timezone-aware datetime
    - naive datetime, interpreted as UTC
    - ISO-8601 string
    - ISO-8601 string ending in Z

    Missing or invalid values return None so one malformed record
    does not fail the complete collection run.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


# ============================================================
# Numeric Parsing
# ============================================================
def parse_non_negative_integer(
    value: object,
) -> int | None:
    """
    Parse a non-negative integer without losing valid zero values.

    Examples:
        0         -> 0
        "0"       -> 0
        15        -> 15
        "15"      -> 15
        None      -> None
        True      -> None
        -1        -> None
        "invalid" -> None
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return None

    return parsed


def get_first_present_value(
    data: dict[str, Any],
    *keys: str,
) -> object:
    """
    Return the first present non-None value.

    Unlike the `or` operator, this helper preserves valid falsy
    values such as numeric zero and empty collections.
    """

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return None


# ============================================================
# Text Normalization
# ============================================================
def normalize_text(
    value: object,
) -> str | None:
    """
    Strip text and convert empty values to None.

    Unicode text, including Arabic and emoji, is preserved.
    """

    if not isinstance(value, str):
        return None

    normalized = value.strip()

    return normalized or None


def normalize_external_identifier(
    value: object,
) -> str | None:
    """
    Strip an external platform identifier without changing case.

    External IDs such as Instagram shortcodes may be case-sensitive.
    """

    return normalize_text(value)


def normalize_connector_type(
    value: object,
) -> str | None:
    """
    Normalize a connector identifier to lowercase.

    Examples:
        " APIFY "       -> "apify"
        "OFFICIAL_API"  -> "official_api"
    """

    normalized = normalize_text(value)

    if normalized is None:
        return None

    return normalized.lower()


# ============================================================
# Ordered String-List Normalization
# ============================================================
def normalize_string_list(
    values: object,
    *,
    remove_social_prefix: bool = False,
) -> list[str]:
    """
    Normalize and deduplicate an ordered list of strings.

    Behavior:
    - Ignores non-list input.
    - Ignores non-string items.
    - Strips whitespace.
    - Removes empty values.
    - Optionally removes one leading # or @.
    - Deduplicates case-insensitively.
    - Preserves the casing and order of the first occurrence.
    """

    if not isinstance(values, list):
        return []

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        normalized = value.strip()

        if (
            remove_social_prefix
            and normalized.startswith(("#", "@"))
        ):
            normalized = normalized[1:].strip()

        if not normalized:
            continue

        deduplication_key = normalized.casefold()

        if deduplication_key in seen:
            continue

        seen.add(deduplication_key)
        normalized_values.append(normalized)

    return normalized_values


def merge_string_lists(
    *collections: object,
    remove_social_prefix: bool = False,
) -> list[str]:
    """
    Merge multiple list-like values into one ordered unique list.

    Useful for combining Instagram image URLs and video URLs.
    """

    merged: list[object] = []

    for collection in collections:
        if isinstance(collection, list):
            merged.extend(collection)

    return normalize_string_list(
        merged,
        remove_social_prefix=remove_social_prefix,
    )


# ============================================================
# Emoji and Information-Quality Helpers
# ============================================================
def is_emoji_only_text(
    text: str,
) -> bool:
    """
    Return True when text contains no letters or digits.

    Examples:
        "😍😍😍" -> True
        "!!!"    -> True
        "Great!" -> False
        "امتى؟" -> False
        "123"    -> False

    This is a structural classifier, not sentiment analysis.
    """

    return not any(
        character.isalpha() or character.isdigit()
        for character in text
    )


def infer_information_quality(
    text: str,
) -> InformationQuality:
    """
    Estimate the structural information richness of a text.

    High:
        Contains a question or at least five word tokens.

    Medium:
        Contains at least two word tokens.

    Low:
        Emoji-only, punctuation-only, empty, or one-word reaction.

    This function does not classify positivity or negativity.
    """

    normalized = text.strip()

    if not normalized:
        return "low"

    if is_emoji_only_text(normalized):
        return "low"

    words = re.findall(
        r"\w+",
        normalized,
        flags=re.UNICODE,
    )

    if "?" in normalized or "؟" in normalized:
        return "high"

    if len(words) >= 5:
        return "high"

    if len(words) >= 2:
        return "medium"

    return "low"


# ============================================================
# Raw-Data Minimization
# ============================================================
def build_minimized_raw_data(
    *,
    source_platform: str,
    allowed_fields: dict[str, object],
) -> dict[str, object]:
    """
    Build a minimized traceability payload.

    The caller explicitly chooses the allowed fields. This prevents
    normalizers from copying complete author profiles or unnecessarily
    large connector payloads into normalized data.
    """

    minimized: dict[str, object] = {
        "source_platform": source_platform,
    }

    for key, value in allowed_fields.items():
        if value is not None:
            minimized[key] = value

    return minimized