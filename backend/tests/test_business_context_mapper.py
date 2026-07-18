"""
Business Creative Context Mapper Tests
"""

from uuid import uuid4

import pytest

from app.creative_context.business_context_mapper import (
    map_business_to_creative_context,
)
from app.creative_context.exceptions import (
    BusinessCreativeContextError,
)
from app.models.pg.business import Business


def _business(
    *,
    country_code: str | None = "sa",
    is_active: bool = True,
    business_metadata: dict | None = None,
) -> Business:
    """Build one in-memory SQLAlchemy Business."""

    return Business(
        id=uuid4(),
        owner_id=uuid4(),
        name="Volume Cafe",
        business_type=" FOOD_AND_BEVERAGE ",
        industry=" cafe ",
        location=" Riyadh ",
        country_code=country_code,
        business_metadata=(
            business_metadata
            if business_metadata is not None
            else {}
        ),
        is_active=is_active,
    )


def test_maps_business_model_to_creative_context():
    """The PostgreSQL business should map to the engine contract."""

    business = _business(
        business_metadata={
            "brand_rules": [
                "Preserve brand colors",
                "Keep packaging recognizable",
            ],
            "supports_seasonal_campaigns": True,
        }
    )

    context = (
        map_business_to_creative_context(
            business
        )
    )

    assert context.business_id == business.id

    assert (
        context.business_type
        == "food_and_beverage"
    )

    assert context.industry == "cafe"

    assert context.country_code == "SA"

    assert context.location == "Riyadh"

    assert context.brand_rules == [
        "Preserve brand colors",
        "Keep packaging recognizable",
    ]

    assert (
        context.business_metadata[
            "supports_seasonal_campaigns"
        ]
        is True
    )


def test_duplicate_brand_rules_are_removed():
    """Repeated brand rules should not leak into the handoff."""

    context = (
        map_business_to_creative_context(
            _business(
                business_metadata={
                    "brand_rules": [
                        "Preserve brand colors",
                        "Preserve brand colors",
                        " ",
                    ]
                }
            )
        )
    )

    assert context.brand_rules == [
        "Preserve brand colors",
    ]


def test_nested_metadata_is_not_copied():
    """Only scalar metadata should enter the minimized context."""

    context = (
        map_business_to_creative_context(
            _business(
                business_metadata={
                    "brand_rules": [],
                    "segment": "premium",
                    "nested": {
                        "unsafe": "value",
                    },
                    "items": [
                        "one",
                    ],
                }
            )
        )
    )

    assert (
        context.business_metadata
        == {
            "segment": "premium",
        }
    )


def test_missing_country_code_is_rejected():
    """Automatic theme resolution requires an explicit country."""

    with pytest.raises(
        BusinessCreativeContextError,
        match="country_code is required",
    ):
        map_business_to_creative_context(
            _business(
                country_code=None,
            )
        )


def test_invalid_country_code_is_rejected():
    """Free-text country values must not be guessed."""

    with pytest.raises(
        BusinessCreativeContextError,
        match="ISO alpha-2",
    ):
        map_business_to_creative_context(
            _business(
                country_code="Saudi Arabia",
            )
        )


def test_inactive_business_is_rejected():
    """Inactive businesses should not start automated generation."""

    with pytest.raises(
        BusinessCreativeContextError,
        match="Inactive businesses",
    ):
        map_business_to_creative_context(
            _business(
                is_active=False,
            )
        )


def test_invalid_brand_rules_are_rejected():
    """Brand rules must retain a stable list contract."""

    with pytest.raises(
        BusinessCreativeContextError,
        match="must be a list",
    ):
        map_business_to_creative_context(
            _business(
                business_metadata={
                    "brand_rules": (
                        "Preserve colors"
                    ),
                }
            )
        )