"""
Market Moment Registry Tests
"""

import json

import pytest

from app.creative_context.exceptions import (
    DuplicateMomentKeyError,
    MomentNotFoundError,
    MomentRegistryError,
)
from app.creative_context.moment_registry import (
    MarketMomentRegistry,
    load_default_moment_registry,
)


EXPECTED_MOMENT_KEYS = {
    "summer",
    "autumn",
    "winter",
    "spring",
    "ramadan",
    "eid_al_fitr",
    "eid_al_adha",
    "valentines",
    "new_year",
    "mother_day",
    "black_friday",
    "white_friday",
    "back_to_school",
    "graduation",
    "saudi_national_day",
    "uae_national_day",
}


def test_default_registry_loads_all_moments():
    registry = (
        load_default_moment_registry()
    )

    assert registry.registry_version == "1.0"

    assert {
        moment.key
        for moment in registry.list_enabled()
    } == EXPECTED_MOMENT_KEYS


def test_summer_definition_uses_country_season():
    registry = (
        load_default_moment_registry()
    )

    summer = registry.get(
        "SUMMER"
    )

    assert (
        summer.date_rule.rule_type
        == "country_season"
    )

    assert (
        summer.date_rule.season_key
        == "summer"
    )

    assert (
        "food_and_beverage"
        in summer.high_fit_business_types
    )

    assert (
        "bright"
        in summer.visual_tokens
    )


def test_ramadan_uses_hijri_rule():
    registry = (
        load_default_moment_registry()
    )

    ramadan = registry.get(
        "ramadan"
    )

    assert (
        ramadan.moment_type
        == "religious"
    )

    assert (
        ramadan.date_rule.rule_type
        == "hijri_annual_range"
    )

    assert (
        ramadan.date_rule
        .hijri_start_month
        == 9
    )


def test_national_moments_are_country_scoped():
    registry = (
        load_default_moment_registry()
    )

    saudi = registry.get(
        "saudi_national_day"
    )

    uae = registry.get(
        "uae_national_day"
    )

    assert (
        saudi.applicable_countries
        == ["SA"]
    )

    assert (
        uae.applicable_countries
        == ["AE"]
    )


def test_unknown_moment_raises_explicit_error():
    registry = (
        load_default_moment_registry()
    )

    with pytest.raises(
        MomentNotFoundError,
        match="unknown_moment",
    ):
        registry.get(
            "unknown_moment"
        )

    assert (
        registry.contains(
            "unknown_moment"
        )
        is False
    )


def test_duplicate_moment_key_is_rejected(
    tmp_path,
):
    config_path = (
        tmp_path
        / "moments.json"
    )

    moment = {
        "key": "summer",
        "display_name": "Summer",
        "moment_type": "season",
        "date_rule": {
            "rule_type": (
                "country_season"
            ),
            "season_key": "summer",
        },
    }

    config_path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "moments": [
                    moment,
                    moment,
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DuplicateMomentKeyError,
    ):
        (
            MarketMomentRegistry
            .from_json_file(
                config_path
            )
        )


def test_invalid_definition_is_rejected(
    tmp_path,
):
    config_path = (
        tmp_path
        / "moments.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "moments": [
                    {
                        "key": (
                            "invalid moment"
                        ),
                        "display_name": (
                            "Invalid"
                        ),
                        "moment_type": (
                            "commercial"
                        ),
                        "date_rule": {
                            "rule_type": (
                                "fixed_annual_range"
                            )
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MomentRegistryError,
        match="validation failed",
    ):
        (
            MarketMomentRegistry
            .from_json_file(
                config_path
            )
        )
