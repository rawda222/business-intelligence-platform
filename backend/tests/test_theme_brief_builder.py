"""
Creative Theme Brief Builder Tests
"""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.creative_context.moment_resolver import (
    resolve_market_moments,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    MomentResolutionRequest,
)
from app.creative_context.theme_brief_builder import (
    build_theme_resolution_result,
)
from app.creative_context.theme_selector import (
    select_theme_moments,
)


_FIXED_RESOLUTION_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

_FIXED_GENERATED_AT = datetime(
    2026,
    7,
    18,
    9,
    0,
    tzinfo=UTC,
)


def _business(
    *,
    business_type: str = (
        "food_and_beverage"
    ),
) -> BusinessCreativeContext:
    """Build a minimal business context."""

    return BusinessCreativeContext(
        business_id=uuid4(),
        business_type=business_type,
        industry="cafe",
        country_code="SA",
        brand_rules=[
            "Preserve brand colors",
            "Keep the product recognizable",
            "Preserve brand colors",
        ],
    )


def _request(
    *,
    selection_mode: str = "automatic",
) -> MomentResolutionRequest:
    """Build a July campaign request."""

    return MomentResolutionRequest(
        campaign_date=date(
            2026,
            7,
            18,
        ),
        target_country_code="SA",
        platform="instagram",
        content_format="feed_post",
        objective="awareness",
        selection_mode=selection_mode,
    )


def _build_result(
    *,
    request: MomentResolutionRequest,
    business: BusinessCreativeContext,
):
    """Run resolution, selection, and brief construction."""

    collection = resolve_market_moments(
        request=request,
        business=business,
    )

    decision = select_theme_moments(
        request=request,
        collection=collection,
    )

    return build_theme_resolution_result(
        request=request,
        business=business,
        collection=collection,
        decision=decision,
        registry_version=(
            "countries:1.0;"
            "moments:1.0"
        ),
        resolution_id=(
            _FIXED_RESOLUTION_ID
        ),
        generated_at=(
            _FIXED_GENERATED_AT
        ),
    )


def test_builds_primary_summer_theme():
    """A Saudi July cafe campaign should produce Summer."""

    request = _request()
    business = _business()

    result = _build_result(
        request=request,
        business=business,
    )

    assert result.primary_theme is not None

    assert (
        result.primary_theme.theme_key
        == "summer"
    )

    assert (
        result.primary_theme.status
        == "active"
    )

    assert (
        result.primary_theme.business_fit
        == "high"
    )

    assert (
        result.primary_theme
        .target_country_code
        == "SA"
    )


def test_brief_contains_country_and_market_context():
    """The brief should expose country and market memberships."""

    result = _build_result(
        request=_request(),
        business=_business(),
    )

    primary = result.primary_theme

    assert primary is not None

    assert primary.market_groups == [
        "GCC",
        "MENA",
        "EMEA",
    ]

    assert (
        "target country SA"
        in primary.constraints
        .market_rules[0]
    )


def test_brief_preserves_unique_brand_rules():
    """Repeated brand rules should be removed safely."""

    result = _build_result(
        request=_request(),
        business=_business(),
    )

    primary = result.primary_theme

    assert primary is not None

    assert (
        primary.constraints.brand_rules
        == [
            "Preserve brand colors",
            (
                "Keep the product "
                "recognizable"
            ),
        ]
    )


def test_brief_contains_visual_tokens_and_constraints():
    """The selected moment should drive visual guidance."""

    result = _build_result(
        request=_request(),
        business=_business(),
    )

    primary = result.primary_theme

    assert primary is not None

    assert (
        "bright"
        in primary.creative_direction
        .visual_tokens
    )

    assert (
        "fresh"
        in primary.creative_direction
        .mood_keywords
    )

    assert (
        "competitor branding"
        in primary.constraints
        .avoid_elements
    )

    assert (
        "generic tropical clichés"
        in primary.constraints
        .avoid_elements
    )


def test_result_is_versioned_and_serializable():
    """The image-team handoff should serialize as stable JSON."""

    business = _business()

    result = _build_result(
        request=_request(),
        business=business,
    )

    payload = result.model_dump(
        mode="json",
    )

    assert (
        payload["contract_version"]
        == "1.0"
    )

    assert (
        payload["registry_version"]
        == (
            "countries:1.0;"
            "moments:1.0"
        )
    )

    assert (
        payload["resolution_id"]
        == str(
            _FIXED_RESOLUTION_ID
        )
    )

    assert (
        payload["generated_at"]
        == (
            "2026-07-18T09:00:00Z"
        )
    )

    assert (
        payload["business_id"]
        == str(
            business.business_id
        )
    )


def test_brand_only_returns_fallback_without_theme():
    """Brand-only mode should return no seasonal brief."""

    request = _request(
        selection_mode="brand_only",
    )

    result = _build_result(
        request=request,
        business=_business(),
    )

    assert result.primary_theme is None

    assert result.secondary_accents == []

    assert result.fallback.allowed is True

    assert (
        result.fallback.theme_key
        == "brand_only"
    )

    assert (
        "brand-only"
        in result.fallback.reason.lower()
    )