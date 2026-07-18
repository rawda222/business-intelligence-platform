"""
Automatic Creative Theme Service Tests
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.creative_context.auto_context_builder import (
    AutoCreativeSignals,
)
from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
)
from app.models.pg.business import Business
from app.models.pg.social_account import SocialAccount


_FIXED_TIME = datetime(
    2026,
    7,
    18,
    9,
    0,
    tzinfo=UTC,
)

_FIXED_RESOLUTION_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


def _business() -> Business:
    """Build one in-memory PostgreSQL business."""

    return Business(
        id=UUID(
            "55555555-5555-5555-5555-555555555555"
        ),
        owner_id=uuid4(),
        name="Volume Cafe",
        business_type="food_and_beverage",
        industry="cafe",
        location="Riyadh",
        country_code="SA",
        business_metadata={
            "brand_rules": [
                "Preserve brand colors",
            ]
        },
        is_active=True,
    )


def _account(
    *,
    business_id: UUID,
    platform: str,
    status: str = "connected",
    is_active: bool = True,
) -> SocialAccount:
    """Build one in-memory social account."""

    return SocialAccount(
        id=uuid4(),
        business_id=business_id,
        platform=platform,
        platform_account_id=str(uuid4()),
        account_name="Test Account",
        connector_type="apify",
        account_metadata={},
        is_active=is_active,
        connection_status=status,
    )


def test_service_resolves_theme_without_user_context():
    """Business data alone should produce the image-team contract."""

    business = _business()

    result = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[
            _account(
                business_id=business.id,
                platform="instagram",
            ),
        ],
        current_time=_FIXED_TIME,
        generated_at=_FIXED_TIME,
        resolution_id=_FIXED_RESOLUTION_ID,
    )

    assert (
        result.automatic_context.request.selection_mode
        == "automatic"
    )

    assert (
        result.automatic_context.request.platform
        == "instagram"
    )

    assert (
        result.theme_result.primary_theme
        is not None
    )

    assert (
        result.theme_result.primary_theme.theme_key
        == "summer"
    )


def test_service_excludes_pending_accounts():
    """Pending accounts should trigger the documented fallback."""

    business = _business()

    result = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[
            _account(
                business_id=business.id,
                platform="facebook",
                status="pending",
            ),
        ],
        current_time=_FIXED_TIME,
    )

    assert (
        result.social_platform_context.platforms
        == ()
    )

    assert (
        result.automatic_context.request.platform
        == "instagram"
    )

    assert result.theme_result.warnings


def test_service_uses_strategy_and_performance_signals():
    """Optional trusted signals should override safe defaults."""

    business = _business()

    signals = AutoCreativeSignals(
        preferred_platform="facebook",
        preferred_content_format="carousel",
        objective="sales",
        product_context="cold beverage",
        platform_source="business_performance",
        format_source="business_performance",
        objective_source="approved_strategy",
        product_source="approved_strategy",
        evidence_references=(
            "trend:format-performance",
            "strategy:current",
        ),
    )

    result = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[
            _account(
                business_id=business.id,
                platform="facebook",
            ),
        ],
        signals=signals,
        current_time=_FIXED_TIME,
    )

    request = result.automatic_context.request

    assert request.platform == "facebook"

    assert (
        request.content_format
        == "carousel"
    )

    assert request.objective == "sales"

    assert (
        request.product_context
        == "cold beverage"
    )


def test_service_exposes_combined_registry_versions():
    """The handoff should identify each registry version."""

    business = _business()

    result = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[],
        current_time=_FIXED_TIME,
    )

    assert (
        result.theme_result.registry_version
        == (
            "countries:1.0;"
            "moments:1.0;"
            "overrides:1.0"
        )
    )


def test_service_is_deterministic_with_fixed_inputs():
    """Fixed IDs and timestamps should produce equal JSON payloads."""

    business = _business()

    first = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[],
        current_time=_FIXED_TIME,
        generated_at=_FIXED_TIME,
        resolution_id=_FIXED_RESOLUTION_ID,
    )

    second = resolve_automatic_creative_theme(
        business=business,
        social_accounts=[],
        current_time=_FIXED_TIME,
        generated_at=_FIXED_TIME,
        resolution_id=_FIXED_RESOLUTION_ID,
    )

    assert (
        first.theme_result.model_dump(mode="json")
        == second.theme_result.model_dump(mode="json")
    )