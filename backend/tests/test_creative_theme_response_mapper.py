"""
Automatic Creative Theme Response Mapper Tests
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
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


def _business() -> Business:
    """Build one in-memory business."""

    return Business(
        id=UUID(
            "66666666-6666-6666-6666-666666666666"
        ),
        owner_id=uuid4(),
        name="Volume Cafe",
        business_type=(
            "food_and_beverage"
        ),
        industry="cafe",
        location="Riyadh",
        country_code="SA",
        business_metadata={},
        is_active=True,
    )


def _account(
    *,
    business_id: UUID,
) -> SocialAccount:
    """Build one connected Instagram account."""

    return SocialAccount(
        id=UUID(
            "77777777-7777-7777-7777-777777777777"
        ),
        business_id=business_id,
        platform="instagram",
        platform_account_id="ig-1",
        account_name="Volume Cafe",
        connector_type="apify",
        account_metadata={},
        is_active=True,
        connection_status="connected",
    )


def test_mapper_builds_json_serializable_contract():
    """The mapped response should serialize for FastAPI."""

    business = _business()

    internal_result = (
        resolve_automatic_creative_theme(
            business=business,
            social_accounts=[
                _account(
                    business_id=business.id
                )
            ],
            current_time=_FIXED_TIME,
            generated_at=_FIXED_TIME,
        )
    )

    response = (
        map_automatic_creative_theme_response(
            internal_result
        )
    )

    payload = response.model_dump(
        mode="json"
    )

    assert (
        payload["theme_result"][
            "primary_theme"
        ]["theme_key"]
        == "summer"
    )

    assert (
        payload["automatic_context"][
            "request"
        ]["selection_mode"]
        == "automatic"
    )

    assert (
        payload["automatic_context"][
            "platform"
        ]["value"]
        == "instagram"
    )

    assert (
        payload[
            "social_platform_context"
        ]["platforms"]
        == ["instagram"]
    )

    assert (
        payload[
            "social_platform_context"
        ]["usable_account_ids"]
        == [
            (
                "77777777-7777-7777-"
                "7777-777777777777"
            )
        ]
    )


def test_mapper_preserves_fallback_warnings():
    """Missing accounts should expose fallback warnings."""

    business = _business()

    internal_result = (
        resolve_automatic_creative_theme(
            business=business,
            social_accounts=[],
            current_time=_FIXED_TIME,
        )
    )

    response = (
        map_automatic_creative_theme_response(
            internal_result
        )
    )

    assert (
        response
        .social_platform_context
        .warnings
    )

    assert response.theme_result.warnings
