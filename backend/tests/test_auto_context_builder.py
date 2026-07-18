"""
Automatic Campaign Context Builder Tests
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.creative_context.auto_context_builder import (
    AutoCreativeSignals,
    build_automatic_campaign_context,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
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
    *,
    industry: str | None = "cafe",
) -> BusinessCreativeContext:
    """Build one automatic creative business context."""

    return BusinessCreativeContext(
        business_id=uuid4(),
        business_type=(
            "food_and_beverage"
        ),
        industry=industry,
        country_code="SA",
        location="Riyadh",
    )


def test_builds_request_without_user_input():
    """The builder should generate every engine request field."""

    result = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[
            "facebook",
            "instagram",
        ],
        current_time=_FIXED_TIME,
    )

    request = result.request

    assert (
        request.campaign_date.isoformat()
        == "2026-07-18"
    )

    assert (
        request.target_country_code
        == "SA"
    )

    assert request.platform == "instagram"

    assert (
        request.content_format
        == "feed_post"
    )

    assert request.objective == "awareness"

    assert request.product_context == "cafe"

    assert (
        request.selection_mode
        == "automatic"
    )


def test_platform_selection_is_deterministic():
    """Configured platform priority must not depend on input order."""

    first = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[
            "facebook",
            "instagram",
        ],
        current_time=_FIXED_TIME,
    )

    second = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[
            "instagram",
            "facebook",
        ],
        current_time=_FIXED_TIME,
    )

    assert (
        first.request.platform
        == second.request.platform
        == "instagram"
    )


def test_no_platform_uses_documented_fallback():
    """Missing social accounts should not block seasonal context."""

    result = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[],
        current_time=_FIXED_TIME,
    )

    assert result.request.platform == "instagram"

    assert result.warnings

    assert (
        result.platform.confidence
        == 0.40
    )


def test_industry_is_product_context_fallback():
    """Business industry should provide the first safe product context."""

    result = build_automatic_campaign_context(
        business=_business(
            industry="cafe",
        ),
        connected_platforms=[
            "instagram",
        ],
        current_time=_FIXED_TIME,
    )

    assert (
        result.request.product_context
        == "cafe"
    )

    assert (
        result.product_context.source
        == "business_industry_fallback"
    )


def test_business_type_is_final_product_fallback():
    """Business type should be used when industry is unavailable."""

    result = build_automatic_campaign_context(
        business=_business(
            industry=None,
        ),
        connected_platforms=[
            "instagram",
        ],
        current_time=_FIXED_TIME,
    )

    assert (
        result.request.product_context
        == "food_and_beverage"
    )

    assert (
        result.product_context.source
        == "business_type_fallback"
    )


def test_strategy_and_performance_signals_override_defaults():
    """Higher-priority signals should override fallback policies."""

    signals = AutoCreativeSignals(
        preferred_platform="facebook",
        preferred_content_format="carousel",
        objective="sales",
        product_context="cold beverage",
        platform_source=(
            "business_performance"
        ),
        format_source=(
            "business_performance"
        ),
        objective_source=(
            "approved_strategy"
        ),
        product_source=(
            "approved_strategy"
        ),
        evidence_references=(
            "strategy:current",
            "trend:format-performance",
        ),
    )

    result = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[
            "facebook",
            "instagram",
        ],
        signals=signals,
        current_time=_FIXED_TIME,
    )

    assert result.request.platform == "facebook"

    assert (
        result.request.content_format
        == "carousel"
    )

    assert result.request.objective == "sales"

    assert (
        result.request.product_context
        == "cold beverage"
    )

    assert result.evidence_references == (
        "strategy:current",
        "trend:format-performance",
    )


def test_field_provenance_is_exposed():
    """Every automatically generated field should explain its source."""

    result = build_automatic_campaign_context(
        business=_business(),
        connected_platforms=[
            "instagram",
        ],
        current_time=_FIXED_TIME,
    )

    assert (
        result.campaign_date.source
        == (
            "business_timezone_"
            "current_date"
        )
    )

    assert (
        result.target_country_code.source
        == "business_profile"
    )

    assert (
        result.platform.source
        == "connected_platform_policy"
    )

    assert (
        result.objective.source
        == "default_policy"
    )