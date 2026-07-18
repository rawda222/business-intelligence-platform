"""
Market Moment Date Resolver Tests
"""

import json
from datetime import date

import pytest

from app.creative_context.country_registry import (
    load_default_country_registry,
)
from app.creative_context.date_resolvers import (
    MomentDateOverrideRegistry,
    load_default_moment_overrides,
    resolve_moment_window,
)
from app.creative_context.exceptions import (
    MomentDateOverrideError,
    MomentDateResolutionError,
)
from app.creative_context.moment_registry import (
    load_default_moment_registry,
)
from app.creative_context.schemas import (
    MarketMomentDefinition,
    MomentDateRule,
)


@pytest.fixture
def country_registry():
    """Load the production country registry."""

    return load_default_country_registry()


@pytest.fixture
def moment_registry():
    """Load the production market-moment registry."""

    return load_default_moment_registry()


def test_default_override_registry_loads():
    """The production override registry should load."""
    overrides = (
        load_default_moment_overrides()
    )

    assert (
        overrides.registry_version
        == "1.1"
    )


def test_sa_summer_is_active_in_july(
    country_registry,
    moment_registry,
):
    """Saudi summer should be active during July."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            7,
            18,
        ),
    )

    assert window.status == "active"

    assert window.active_from == date(
        2026,
        6,
        1,
    )

    assert window.active_until == date(
        2026,
        8,
        31,
    )

    assert (
        window.date_source
        == "country_season"
    )


def test_cross_year_winter_is_active_in_january(
    country_registry,
    moment_registry,
):
    """A December-to-February winter must resolve across years."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "winter"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            1,
            15,
        ),
    )

    assert window.status == "active"

    assert window.active_from == date(
        2025,
        12,
        1,
    )

    assert window.active_until == date(
        2026,
        2,
        28,
    )


def test_valentines_is_upcoming_inside_lead_window(
    country_registry,
    moment_registry,
):
    """Valentine's should be upcoming inside its lead window."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "valentines"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            1,
            20,
        ),
    )

    assert window.status == "upcoming"

    assert window.active_from == date(
        2026,
        2,
        1,
    )


def test_valentines_cooldown_is_resolved(
    country_registry,
    moment_registry,
):
    """The configured day after Valentine's should be cooldown."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "valentines"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            2,
            15,
        ),
    )

    assert window.status == "cooldown"


def test_new_year_cross_year_range_is_active(
    country_registry,
    moment_registry,
):
    """New Year should resolve from December into January."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "new_year"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            12,
            20,
        ),
    )

    assert window.status == "active"

    assert window.active_until == date(
        2027,
        1,
        1,
    )


def test_ramadan_hijri_window_is_resolved(
    country_registry,
    moment_registry,
):
    """Ramadan should resolve through the Hijri calendar rule."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "ramadan"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            2,
            18,
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "hijri_annual_range"
    )

    assert (
        window.active_from
        <= window.active_until
    )


def test_explicit_date_range_is_resolved(
    country_registry,
):
    """An explicit temporary campaign range should resolve."""

    moment = MarketMomentDefinition(
        key="temporary_campaign",
        display_name=(
            "Temporary Campaign"
        ),
        moment_type="commercial",
        date_rule=MomentDateRule(
            rule_type=(
                "explicit_date_range"
            ),
            explicit_start=date(
                2026,
                7,
                1,
            ),
            explicit_end=date(
                2026,
                7,
                31,
            ),
        ),
        lead_days=0,
        cooldown_days=0,
    )

    window = resolve_moment_window(
        moment=moment,
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            7,
            18,
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "explicit_date_range"
    )


def test_country_specific_date_requires_override(
    country_registry,
    moment_registry,
):
    """
    A country-specific event without an override must fail clearly.
    """

    with pytest.raises(
        MomentDateResolutionError,
        match=(
            "requires a country/year override"
        ),
    ):
        resolve_moment_window(
            moment=moment_registry.get(
                "graduation"
            ),
            country=country_registry.get(
                "SA"
            ),
            campaign_date=date(
                2026,
                6,
                1,
            ),
        )


def test_country_year_override_takes_precedence(
    tmp_path,
    country_registry,
    moment_registry,
):
    """An exact country/year override should replace the rule."""

    path = (
        tmp_path
        / "moment_overrides.json"
    )

    path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "overrides": [
                    {
                        "country_code": "SA",
                        "moment_key": (
                            "back_to_school"
                        ),
                        "year": 2026,
                        "active_from": (
                            "2026-08-20"
                        ),
                        "active_until": (
                            "2026-08-23"
                        ),
                        "source": (
                            "test_calendar"
                        ),
                        "version": "1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    overrides = (
        MomentDateOverrideRegistry
        .from_json_file(
            path
        )
    )

    window = resolve_moment_window(
        moment=moment_registry.get(
            "back_to_school"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            8,
            22,
        ),
        overrides=overrides,
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "country_year_override"
    )

    assert window.active_from == date(
        2026,
        8,
        20,
    )


def test_duplicate_override_is_rejected(
    tmp_path,
):
    """Duplicate country/moment/year override keys must fail."""

    path = (
        tmp_path
        / "moment_overrides.json"
    )

    override = {
        "country_code": "SA",
        "moment_key": "summer",
        "year": 2026,
        "active_from": "2026-06-01",
        "active_until": "2026-08-31",
        "source": "test",
    }

    path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "overrides": [
                    override,
                    override,
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MomentDateOverrideError,
        match="Duplicate",
    ):
        (
            MomentDateOverrideRegistry
            .from_json_file(
                path
            )
        )
def test_sa_back_to_school_uses_2026_override(
    country_registry,
    moment_registry,
):
    """Saudi back-to-school should use the approved 2026 date."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "back_to_school"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            8,
            23,
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "country_year_override"
    )

    assert window.active_from == date(
        2026,
        8,
        23,
    )

    assert window.active_until == date(
        2026,
        8,
        23,
    )


def test_sa_black_friday_uses_2026_override(
    country_registry,
    moment_registry,
):
    """Saudi Black Friday should use the approved 2026 date."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "black_friday"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            11,
            27,
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "country_year_override"
    )


def test_sa_white_friday_uses_product_policy_override(
    country_registry,
    moment_registry,
):
    """Saudi White Friday should follow the approved product policy."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "white_friday"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            11,
            27,
        ),
    )

    assert window.status == "active"

    assert (
        window.date_source
        == "country_year_override"
    )


def test_mother_day_uses_fixed_annual_date(
    country_registry,
    moment_registry,
):
    """Mother's Day should resolve annually on March 21."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "mother_day"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            3,
            21,
        ),
    )

    assert window.status == "active"

    assert window.active_from == date(
        2026,
        3,
        21,
    )

    assert window.active_until == date(
        2026,
        3,
        21,
    )

    assert (
    window.date_source
    == "fixed_annual_range"
)


def test_saudi_national_day_uses_fixed_annual_date(
    country_registry,
    moment_registry,
):
    """Saudi National Day should resolve annually on September 23."""

    window = resolve_moment_window(
        moment=moment_registry.get(
            "saudi_national_day"
        ),
        country=country_registry.get(
            "SA"
        ),
        campaign_date=date(
            2026,
            9,
            23,
        ),
    )

    assert window.status == "active"

    assert window.active_from == date(
        2026,
        9,
        23,
    )

    assert window.active_until == date(
        2026,
        9,
        23,
    )

    assert (
        window.date_source
        == "fixed_annual_range"
    )