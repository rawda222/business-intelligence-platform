"""
Automatic Creative Theme API Tests
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import creative_themes
from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
)
from app.creative_context.exceptions import (
    BusinessCreativeContextError,
)
from app.models.pg.business import Business
from app.models.pg.social_account import (
    SocialAccount,
)


_BUSINESS_ID = UUID(
    "88888888-8888-8888-8888-888888888888"
)

_OWNER_ID = UUID(
    "99999999-9999-9999-9999-999999999999"
)

_FIXED_TIME = datetime(
    2026,
    7,
    18,
    9,
    0,
    tzinfo=UTC,
)


def _business(
    country_code: str | None = "SA",
) -> Business:
    """Build one owned business."""

    return Business(
        id=_BUSINESS_ID,
        owner_id=_OWNER_ID,
        name="Volume Cafe",
        business_type=(
            "food_and_beverage"
        ),
        industry="cafe",
        location="Riyadh",
        country_code=country_code,
        business_metadata={},
        is_active=True,
    )


def _account() -> SocialAccount:
    """Build one connected Instagram account."""

    return SocialAccount(
        id=uuid4(),
        business_id=_BUSINESS_ID,
        platform="instagram",
        platform_account_id="ig-api-test",
        account_name="Volume Cafe",
        connector_type="apify",
        account_metadata={},
        is_active=True,
        connection_status="connected",
    )


@pytest.mark.asyncio
async def test_endpoint_resolves_owned_business(
    monkeypatch,
):
    """
    An owned business should produce an automatic theme response.
    """

    business = _business()
    account = _account()

    captured: dict[str, object] = {}

    async def fake_get_business_by_id(
        db,
        business_id,
        owner_id,
    ):
        captured["business_id"] = (
            business_id
        )
        captured["owner_id"] = owner_id

        return business

    async def fake_list_accounts(
        db,
        business_id,
    ):
        captured["accounts_business_id"] = (
            business_id
        )

        return [account]

    def fake_resolve(
        business,
        social_accounts,
    ):
        return (
            resolve_automatic_creative_theme(
                business=business,
                social_accounts=(
                    social_accounts
                ),
                current_time=_FIXED_TIME,
                generated_at=_FIXED_TIME,
            )
        )

    monkeypatch.setattr(
        creative_themes,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "list_active_social_"
            "accounts_for_business"
        ),
        fake_list_accounts,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "resolve_automatic_"
            "creative_theme"
        ),
        fake_resolve,
    )

    response = await (
        creative_themes
        .auto_resolve_creative_theme(
            business_id=_BUSINESS_ID,
            current_user=SimpleNamespace(
                id=_OWNER_ID
            ),
            db=object(),
        )
    )

    assert (
        captured["business_id"]
        == _BUSINESS_ID
    )

    assert (
        captured["owner_id"]
        == _OWNER_ID
    )

    assert (
        captured[
            "accounts_business_id"
        ]
        == _BUSINESS_ID
    )

    assert (
        response.theme_result
        .primary_theme
        is not None
    )

    assert (
        response.theme_result
        .primary_theme
        .theme_key
        == "summer"
    )

    assert (
        response.automatic_context
        .platform.value
        == "instagram"
    )


@pytest.mark.asyncio
async def test_endpoint_hides_unowned_business(
    monkeypatch,
):
    """
    A missing or cross-tenant business should return the same 404.
    """

    async def fake_get_business_by_id(
        db,
        business_id,
        owner_id,
    ):
        return None

    monkeypatch.setattr(
        creative_themes,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await (
            creative_themes
            .auto_resolve_creative_theme(
                business_id=_BUSINESS_ID,
                current_user=(
                    SimpleNamespace(
                        id=_OWNER_ID
                    )
                ),
                db=object(),
            )
        )

    assert (
        captured.value.status_code
        == 404
    )

    assert (
        captured.value.detail
        == "Business not found"
    )


@pytest.mark.asyncio
async def test_endpoint_maps_context_error_to_422(
    monkeypatch,
):
    """Invalid business context should become a safe API error."""

    business = _business(
        country_code=None
    )

    async def fake_get_business_by_id(
        db,
        business_id,
        owner_id,
    ):
        return business

    async def fake_list_accounts(
        db,
        business_id,
    ):
        return []

    monkeypatch.setattr(
        creative_themes,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "list_active_social_"
            "accounts_for_business"
        ),
        fake_list_accounts,
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await (
            creative_themes
            .auto_resolve_creative_theme(
                business_id=_BUSINESS_ID,
                current_user=(
                    SimpleNamespace(
                        id=_OWNER_ID
                    )
                ),
                db=object(),
            )
        )

    assert (
        captured.value.status_code
        == 422
    )

    assert (
        "country_code"
        in captured.value.detail
    )


def test_router_is_registered_in_application():
    """The automatic route should be registered in FastAPI."""

    from app.main import app

    route_paths = {
        route.path
        for route in app.routes
    }

    assert (
        "/api/v1/businesses/"
        "{business_id}/creative-themes/"
        "auto-resolve"
        in route_paths
    )
@pytest.mark.asyncio
async def test_image_handoff_endpoint_returns_compact_contract(
    monkeypatch,
):
    """
    An owned business should receive the compact image contract.
    """

    business = _business()
    account = _account()

    async def fake_get_business_by_id(
        db,
        business_id,
        owner_id,
    ):
        assert business_id == _BUSINESS_ID
        assert owner_id == _OWNER_ID

        return business

    async def fake_list_accounts(
        db,
        business_id,
    ):
        assert business_id == _BUSINESS_ID

        return [account]

    def fake_resolve(
        business,
        social_accounts,
    ):
        return (
            resolve_automatic_creative_theme(
                business=business,
                social_accounts=(
                    social_accounts
                ),
                current_time=_FIXED_TIME,
                generated_at=_FIXED_TIME,
            )
        )

    monkeypatch.setattr(
        creative_themes,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "list_active_social_"
            "accounts_for_business"
        ),
        fake_list_accounts,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "resolve_automatic_"
            "creative_theme"
        ),
        fake_resolve,
    )

    response = await (
        creative_themes
        .build_image_generation_handoff(
            business_id=_BUSINESS_ID,
            current_user=SimpleNamespace(
                id=_OWNER_ID
            ),
            db=object(),
        )
    )

    payload = response.model_dump(
        mode="json"
    )

    assert response.theme is not None

    assert (
        response.theme.theme_key
        == "summer"
    )

    assert response.platform == "instagram"

    assert response.product_context == "cafe"

    assert "warnings" not in payload

    assert "resolved_moments" not in payload

    assert "rejected_moments" not in payload

    assert (
        "social_platform_context"
        not in payload
    )

    assert (
        "automatic_context"
        not in payload
    )


def test_image_handoff_route_is_registered():
    """The compact image handoff route should be registered."""

    from app.main import app

    route_paths = {
        route.path
        for route in app.routes
    }

    assert (
        "/api/v1/businesses/"
        "{business_id}/creative-themes/"
        "image-handoff"
        in route_paths
    )

@pytest.mark.asyncio
async def test_image_handoff_endpoint_returns_compact_contract(
    monkeypatch,
):
    """
    An owned business should receive the compact image contract.
    """

    business = _business()
    account = _account()

    async def fake_get_business_by_id(
        db,
        business_id,
        owner_id,
    ):
        assert business_id == _BUSINESS_ID
        assert owner_id == _OWNER_ID

        return business

    async def fake_list_accounts(
        db,
        business_id,
    ):
        assert business_id == _BUSINESS_ID

        return [account]

    def fake_resolve(
        business,
        social_accounts,
    ):
        return (
            resolve_automatic_creative_theme(
                business=business,
                social_accounts=(
                    social_accounts
                ),
                current_time=_FIXED_TIME,
                generated_at=_FIXED_TIME,
            )
        )

    monkeypatch.setattr(
        creative_themes,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "list_active_social_"
            "accounts_for_business"
        ),
        fake_list_accounts,
    )

    monkeypatch.setattr(
        creative_themes,
        (
            "resolve_automatic_"
            "creative_theme"
        ),
        fake_resolve,
    )

    response = await (
        creative_themes
        .build_image_generation_handoff(
            business_id=_BUSINESS_ID,
            current_user=SimpleNamespace(
                id=_OWNER_ID
            ),
            db=object(),
        )
    )

    payload = response.model_dump(
        mode="json"
    )

    assert response.theme is not None

    assert (
        response.theme.theme_key
        == "summer"
    )

    assert response.platform == "instagram"

    assert response.product_context == "cafe"

    assert "warnings" not in payload

    assert "resolved_moments" not in payload

    assert "rejected_moments" not in payload

    assert (
        "social_platform_context"
        not in payload
    )

    assert (
        "automatic_context"
        not in payload
    )


def test_image_handoff_route_is_registered():
    """The compact image handoff route should be registered."""

    from app.main import app

    route_paths = {
        route.path
        for route in app.routes
    }

    assert (
        "/api/v1/businesses/"
        "{business_id}/creative-themes/"
        "image-handoff"
        in route_paths
    )