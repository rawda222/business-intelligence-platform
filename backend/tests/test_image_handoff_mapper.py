"""
Image Generation Handoff Mapper Tests
"""

from datetime import UTC, datetime
from uuid import UUID

from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
)
from app.creative_context.image_handoff_mapper import (
    map_image_generation_handoff,
)
from app.creative_context.response_mapper import (
    map_automatic_creative_theme_response,
)
from app.models.pg.business import Business
from app.models.pg.social_account import (
    SocialAccount,
)


_FIXED_TIME = datetime(
    2026,
    7,
    18,
    9,
    0,
    tzinfo=UTC,
)

_BUSINESS_ID = UUID(
    "11111111-2222-3333-4444-555555555555"
)

_ACCOUNT_ID = UUID(
    "66666666-7777-8888-9999-000000000000"
)

_RESOLUTION_ID = UUID(
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
)


def _build_handoff():
    """Build one deterministic image-generation handoff."""

    business = Business(
        id=_BUSINESS_ID,
        owner_id=UUID(
            "12345678-1234-1234-1234-123456789012"
        ),
        name="Volume Cafe",
        business_type="food_and_beverage",
        industry="cafe",
        location="Riyadh",
        country_code="SA",
        business_metadata={
            "brand_rules": [
                "Preserve brand colors",
                "Keep packaging recognizable",
            ]
        },
        is_active=True,
    )

    account = SocialAccount(
        id=_ACCOUNT_ID,
        business_id=_BUSINESS_ID,
        platform="instagram",
        platform_account_id="image-handoff-account",
        account_name="Volume Cafe",
        connector_type="apify",
        account_metadata={},
        is_active=True,
        connection_status="connected",
    )

    internal_result = (
        resolve_automatic_creative_theme(
            business=business,
            social_accounts=[
                account
            ],
            current_time=_FIXED_TIME,
            generated_at=_FIXED_TIME,
            resolution_id=_RESOLUTION_ID,
        )
    )

    full_response = (
        map_automatic_creative_theme_response(
            internal_result
        )
    )

    return map_image_generation_handoff(
        full_response
    )


def test_handoff_contains_selected_theme():
    """The compact contract should contain the selected theme."""

    handoff = _build_handoff()

    assert handoff.theme is not None

    assert (
        handoff.theme.theme_key
        == "summer"
    )

    assert (
        handoff.theme.business_fit
        == "high"
    )

    assert (
        handoff.platform
        == "instagram"
    )

    assert (
        handoff.product_context
        == "cafe"
    )


def test_handoff_excludes_internal_resolution_data():
    """Audit-only collections must not reach the image team."""

    payload = _build_handoff().model_dump(
        mode="json"
    )

    assert set(
        payload.keys()
    ) == {
        "contract_version",
        "business_id",
        "resolution_id",
        "generated_at",
        "campaign_date",
        "target_country_code",
        "platform",
        "content_format",
        "objective",
        "product_context",
        "theme",
        "fallback",
        "evidence_references",
    }

    assert "resolved_moments" not in payload

    assert "rejected_moments" not in payload

    assert "social_platform_context" not in payload

    assert "automatic_context" not in payload

    assert "warnings" not in payload


def test_handoff_removes_duplicate_evidence():
    """Evidence references should be unique and ordered."""

    handoff = _build_handoff()

    assert (
        len(
            handoff.evidence_references
        )
        == len(
            set(
                handoff.evidence_references
            )
        )
    )

    assert (
        handoff.evidence_references
        == [
            "country-profile:SA:1",
            "moment-definition:summer:1",
            (
                "business-context:"
                "11111111-2222-3333-"
                "4444-555555555555"
            ),
        ]
    )
