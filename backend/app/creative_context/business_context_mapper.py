"""
Business Creative Context Mapper

Maps the PostgreSQL Business model into the minimized,
model-independent BusinessCreativeContext contract.

The mapper does not access social posts, reviews, trends,
strategies, or image-generation models.
"""

from typing import Any

from app.creative_context.exceptions import (
    BusinessCreativeContextError,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
)
from app.models.pg.business import Business


def _normalize_country_code(
    value: str | None,
) -> str:
    """Validate and normalize one ISO alpha-2 country code."""

    if value is None:
        raise BusinessCreativeContextError(
            "Business country_code is required "
            "for automatic creative context."
        )

    normalized = value.strip().upper()

    if (
        len(normalized) != 2
        or not normalized.isalpha()
    ):
        raise BusinessCreativeContextError(
            "Business country_code must use "
            "ISO alpha-2 format."
        )

    return normalized


def _extract_brand_rules(
    metadata: dict[str, Any],
) -> list[str]:
    """Extract clean unique brand rules from business metadata."""

    raw_rules = metadata.get(
        "brand_rules",
        [],
    )

    if raw_rules is None:
        return []

    if not isinstance(
        raw_rules,
        list,
    ):
        raise BusinessCreativeContextError(
            "business_metadata.brand_rules "
            "must be a list."
        )

    rules: list[str] = []

    for item in raw_rules:
        if not isinstance(
            item,
            str,
        ):
            raise BusinessCreativeContextError(
                "Every brand rule must be "
                "a string."
            )

        cleaned = item.strip()

        if (
            cleaned
            and cleaned not in rules
        ):
            rules.append(
                cleaned
            )

    return rules



def _minimize_metadata(
    metadata: dict[str, Any],
) -> dict[
    str,
    str | int | float | bool | None,
]:
    """
    Keep only scalar metadata accepted by the creative contract.

    Nested values remain owned by their source model and are not
    copied blindly into the image-team handoff context.
    """

    scalar_types = (
        str,
        int,
        float,
        bool,
    )

    minimized: dict[
        str,
        str | int | float | bool | None,
    ] = {}

    for key, value in metadata.items():
        if key == "brand_rules":
            continue

        if (
            value is None
            or isinstance(
                value,
                scalar_types,
            )
        ):
            minimized[str(key)] = value

    return minimized


def map_business_to_creative_context(
    business: Business,
) -> BusinessCreativeContext:
    """Map one active PostgreSQL Business into creative context."""

    if not business.is_active:
        raise BusinessCreativeContextError(
            "Inactive businesses cannot use "
            "automatic creative context."
        )

    business_type = (
        business.business_type.strip().lower()
    )

    if not business_type:
        raise BusinessCreativeContextError(
            "Business business_type is required."
        )

    raw_metadata = (
        business.business_metadata
        or {}
    )

    if not isinstance(
        raw_metadata,
        dict,
    ):
        raise BusinessCreativeContextError(
            "Business metadata must be "
            "an object."
        )

    return BusinessCreativeContext(
        business_id=business.id,
        business_type=business_type,
        industry=(
            business.industry.strip()
            if business.industry
            else None
        ),
        country_code=(
            _normalize_country_code(
                business.country_code
            )
        ),
        location=(
            business.location.strip()
            if business.location
            else None
        ),
        brand_rules=(
            _extract_brand_rules(
                raw_metadata
            )
        ),
        business_metadata=(
            _minimize_metadata(
                raw_metadata
            )
        ),
    )