"""
Creative Context Schema Tests

Verifies the stable contracts used by the seasonal creative-context
engine and image-generation handoff.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.creative_context.schemas import (
    CREATIVE_THEME_CONTRACT_VERSION,
    BusinessCreativeContext,
    CountryCreativeProfile,
    CountrySeasonWindow,
    CreativeConstraints,
    CreativeDirection,
    CreativeThemeBrief,
    MarketMomentDefinition,
    MomentDateRule,
    MomentResolutionRequest,
    RejectedMarketMoment,
    ResolvedMarketMoment,
    ThemeFallback,
    ThemeResolutionResult,
    ResolvedMomentWindow
)


def build_summer_definition():
    """Build one valid Summer moment definition."""

    return MarketMomentDefinition(
        key="summer",
        display_name="Summer",
        moment_type="season",
        date_rule=MomentDateRule(
            rule_type="country_season",
            season_key="summer",
        ),
        applicable_market_groups=[
            "GCC",
            "MENA",
        ],
        high_fit_business_types=[
            "food_and_beverage",
            "hospitality",
        ],
        medium_fit_business_types=[
            "retail",
        ],
        low_fit_business_types=[
            "saas",
        ],
        excluded_business_types=[
            "b2b_services",
        ],
        lead_days=21,
        cooldown_days=7,
        priority=70,
        visual_tokens=[
            "bright",
            "fresh",
            "light",
            "refreshing",
        ],
        default_avoid_elements=[
            "generic tropical clichés",
        ],
        version="1",
    )


def test_valid_country_profile():
    profile = CountryCreativeProfile(
        country_code="SA",
        market_groups=[
            "GCC",
            "MENA",
            "EMEA",
            "GCC",
        ],
        hemisphere="northern",
        timezone="Asia/Riyadh",
        languages=[
            "ar",
            "en",
            "ar",
        ],
        season_windows=[
            CountrySeasonWindow(
                season_key="summer",
                start_month=6,
                start_day=1,
                end_month=8,
                end_day=31,
            ),
        ],
    )

    assert profile.country_code == "SA"

    assert profile.market_groups == [
        "GCC",
        "MENA",
        "EMEA",
    ]

    assert profile.languages == [
        "ar",
        "en",
    ]


def test_invalid_country_code_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        CountryCreativeProfile(
            country_code="Saudi Arabia",
            market_groups=[],
            hemisphere="northern",
            timezone="Asia/Riyadh",
            languages=["ar"],
        )


def test_valid_country_season_rule():
    rule = MomentDateRule(
        rule_type="country_season",
        season_key="summer",
    )

    assert rule.season_key == "summer"


def test_country_season_requires_key():
    with pytest.raises(
        ValidationError,
        match="season_key",
    ):
        MomentDateRule(
            rule_type="country_season",
        )


def test_fixed_annual_rule_requires_dates():
    with pytest.raises(
        ValidationError,
        match="fixed_annual_range",
    ):
        MomentDateRule(
            rule_type="fixed_annual_range",
            start_month=2,
            start_day=1,
        )


def test_explicit_range_rejects_reverse_dates():
    with pytest.raises(
        ValidationError,
        match="explicit_end",
    ):
        MomentDateRule(
            rule_type="explicit_date_range",
            explicit_start=date(
                2026,
                7,
                10,
            ),
            explicit_end=date(
                2026,
                7,
                1,
            ),
        )


def test_valid_market_moment_definition():
    moment = build_summer_definition()

    assert moment.key == "summer"
    assert moment.priority == 70

    assert (
        "food_and_beverage"
        in moment.high_fit_business_types
    )


def test_conflicting_business_fit_is_rejected():
    with pytest.raises(
        ValidationError,
        match="multiple fit groups",
    ):
        MarketMomentDefinition(
            key="invalid_moment",
            display_name="Invalid Moment",
            moment_type="commercial",
            date_rule=MomentDateRule(
                rule_type="fixed_annual_range",
                start_month=2,
                start_day=1,
                end_month=2,
                end_day=14,
            ),
            high_fit_business_types=[
                "retail",
            ],
            excluded_business_types=[
                "retail",
            ],
        )


def test_user_override_requires_moment_key():
    with pytest.raises(
        ValidationError,
        match="moment_override",
    ):
        MomentResolutionRequest(
            campaign_date=date(
                2026,
                7,
                18,
            ),
            target_country_code="SA",
            platform="instagram",
            content_format="feed_post",
            objective="awareness",
            selection_mode="user_override",
        )


def test_valid_business_context():
    business_id = uuid4()

    context = BusinessCreativeContext(
        business_id=business_id,
        business_type=(
            "food_and_beverage"
        ),
        industry="cafe",
        country_code="SA",
        location="Riyadh",
        brand_rules=[
            "Preserve brand colors",
        ],
        business_metadata={
            "supports_seasonal_campaigns": (
                True
            ),
        },
    )

    assert context.business_id == business_id
    assert context.country_code == "SA"


def test_not_applicable_moment_cannot_be_eligible():
    with pytest.raises(
        ValidationError,
        match="cannot be eligible",
    ):
        ResolvedMarketMoment(
            key="summer",
            display_name="Summer",
            moment_type="season",
            campaign_date=date(
                2026,
                7,
                18,
            ),
            active_from=date(
                2026,
                6,
                1,
            ),
            active_until=date(
                2026,
                8,
                31,
            ),
            status="active",
            business_fit=(
                "not_applicable"
            ),
            eligible=True,
            priority=70,
            selection_score=0.0,
        )


def test_complete_theme_resolution_contract():
    business_id = uuid4()

    request = MomentResolutionRequest(
        campaign_date=date(
            2026,
            7,
            18,
        ),
        target_country_code="SA",
        platform="instagram",
        content_format="feed_post",
        objective="awareness",
        product_context="cold beverage",
    )

    resolved = ResolvedMarketMoment(
        key="summer",
        display_name="Summer",
        moment_type="season",
        campaign_date=(
            request.campaign_date
        ),
        active_from=date(
            2026,
            6,
            1,
        ),
        active_until=date(
            2026,
            8,
            31,
        ),
        status="active",
        business_fit="high",
        eligible=True,
        priority=70,
        selection_score=0.88,
        visual_tokens=[
            "bright",
            "fresh",
        ],
        reasons=[
            "Summer is active.",
        ],
        evidence_references=[
            "registry:moment:summer:v1",
        ],
    )

    brief = CreativeThemeBrief(
        theme_key=(
            "summer_refreshment"
        ),
        display_name=(
            "Summer Refreshment"
        ),
        source_moment="summer",
        moment_type="season",
        status="active",
        target_country_code="SA",
        market_groups=[
            "GCC",
            "MENA",
            "EMEA",
        ],
        campaign_date=(
            request.campaign_date
        ),
        platform="instagram",
        content_format="feed_post",
        objective="awareness",
        business_fit="high",
        confidence=0.88,
        valid_from=date(
            2026,
            6,
            1,
        ),
        valid_until=date(
            2026,
            8,
            31,
        ),
        creative_direction=(
            CreativeDirection(
                concept=(
                    "Fresh seasonal "
                    "product presentation"
                ),
                mood_keywords=[
                    "bright",
                    "fresh",
                ],
                visual_tokens=[
                    "soft daylight",
                ],
            )
        ),
        constraints=(
            CreativeConstraints(
                brand_rules=[
                    "Preserve brand colors",
                ],
                market_rules=[
                    "Use market-appropriate "
                    "styling",
                ],
                avoid_elements=[
                    "Competitor branding",
                ],
            )
        ),
        reasons=[
            "Summer is active.",
        ],
        evidence_references=[
            "registry:moment:summer:v1",
        ],
    )

    result = ThemeResolutionResult(
        registry_version="1",
        resolution_id=uuid4(),
        generated_at=datetime.now(
            UTC,
        ),
        business_id=business_id,
        request=request,
        primary_theme=brief,
        resolved_moments=[
            resolved,
        ],
        rejected_moments=[
            RejectedMarketMoment(
                key="valentines",
                display_name=(
                    "Valentine's"
                ),
                status="inactive",
                business_fit="high",
                reason=(
                    "Outside the active "
                    "window."
                ),
            ),
        ],
        fallback=ThemeFallback(
            allowed=True,
            theme_key="brand_only",
            reason=(
                "Used when no eligible "
                "moment is available."
            ),
        ),
    )

    serialized = result.model_dump(
        mode="json",
    )

    assert (
        serialized["contract_version"]
        == CREATIVE_THEME_CONTRACT_VERSION
    )

    assert (
        serialized["primary_theme"][
            "theme_key"
        ]
        == "summer_refreshment"
    )

    assert (
        serialized["request"][
            "target_country_code"
        ]
        == "SA"
    )

    assert (
        serialized["fallback"][
            "theme_key"
        ]
        == "brand_only"
    )


def test_unknown_fields_are_rejected():
    with pytest.raises(
        ValidationError,
    ):
        MomentResolutionRequest(
            campaign_date=date(
                2026,
                7,
                18,
            ),
            target_country_code="SA",
            platform="instagram",
            content_format="feed_post",
            objective="awareness",
            unexpected_field=True,
        )

def test_valid_resolved_moment_window():
    window = ResolvedMomentWindow(
        moment_key="summer",
        country_code="SA",
        campaign_date=date(
            2026,
            7,
            18,
        ),
        active_from=date(
            2026,
            6,
            1,
        ),
        active_until=date(
            2026,
            8,
            31,
        ),
        lead_from=date(
            2026,
            5,
            11,
        ),
        cooldown_until=date(
            2026,
            9,
            7,
        ),
        status="active",
        date_source="country_season",
        evidence_reference=(
            "country-profile:SA:v1"
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "country_season"
    )


def test_resolved_window_rejects_invalid_order():
    with pytest.raises(
        ValidationError,
        match="lead_from",
    ):
        ResolvedMomentWindow(
            moment_key="summer",
            country_code="SA",
            campaign_date=date(
                2026,
                7,
                18,
            ),
            active_from=date(
                2026,
                6,
                1,
            ),
            active_until=date(
                2026,
                8,
                31,
            ),
            lead_from=date(
                2026,
                6,
                2,
            ),
            cooldown_until=date(
                2026,
                9,
                7,
            ),
            status="active",
            date_source=(
                "country_season"
            ),
            evidence_reference=(
                "country-profile:SA:v1"
            ),
        )
