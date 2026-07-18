"""
Country Creative Registry Tests
"""

import json

import pytest

from app.creative_context.country_registry import (
    CountryCreativeRegistry,
    load_default_country_registry,
)
from app.creative_context.exceptions import (
    CountryNotFoundError,
    CountryRegistryError,
    DuplicateCountryCodeError,
)


def test_default_registry_loads_launch_countries():
    registry = (
        load_default_country_registry()
    )

    profiles = registry.list_enabled()

    assert registry.registry_version == "1.0"

    assert {
        profile.country_code
        for profile in profiles
    } == {
        "SA",
        "AE",
        "KW",
        "QA",
        "BH",
        "OM",
        "EG",
    }


def test_sa_has_expected_market_membership():
    registry = (
        load_default_country_registry()
    )

    profile = registry.get(
        "sa"
    )

    assert profile.country_code == "SA"

    assert profile.market_groups == [
        "GCC",
        "MENA",
        "EMEA",
    ]

    assert (
        profile.timezone
        == "Asia/Riyadh"
    )

    assert {
        window.season_key
        for window in (
            profile.season_windows
        )
    } == {
        "summer",
        "autumn",
        "winter",
        "spring",
    }


def test_egypt_is_not_classified_as_gcc():
    registry = (
        load_default_country_registry()
    )

    profile = registry.get(
        "EG"
    )

    assert "MENA" in profile.market_groups
    assert "EMEA" in profile.market_groups
    assert "GCC" not in profile.market_groups


def test_unknown_country_raises_explicit_error():
    registry = (
        load_default_country_registry()
    )

    with pytest.raises(
        CountryNotFoundError,
        match="ZZ",
    ):
        registry.get(
            "ZZ"
        )

    assert registry.contains(
        "ZZ"
    ) is False


def test_duplicate_country_code_is_rejected(
    tmp_path,
):
    config_path = (
        tmp_path
        / "countries.json"
    )

    country = {
        "country_code": "SA",
        "market_groups": [
            "GCC",
        ],
        "hemisphere": "northern",
        "timezone": "Asia/Riyadh",
        "languages": [
            "ar",
        ],
        "season_windows": [],
    }

    config_path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "countries": [
                    country,
                    country,
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DuplicateCountryCodeError,
    ):
        (
            CountryCreativeRegistry
            .from_json_file(
                config_path
            )
        )


def test_invalid_timezone_is_rejected(
    tmp_path,
):
    config_path = (
        tmp_path
        / "countries.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "countries": [
                    {
                        "country_code": "SA",
                        "market_groups": [
                            "GCC",
                        ],
                        "hemisphere": (
                            "northern"
                        ),
                        "timezone": (
                            "Invalid/Timezone"
                        ),
                        "languages": [
                            "ar",
                        ],
                        "season_windows": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        CountryRegistryError,
        match="Unknown timezone",
    ):
        (
            CountryCreativeRegistry
            .from_json_file(
                config_path
            )
        )


def test_duplicate_season_key_is_rejected(
    tmp_path,
):
    config_path = (
        tmp_path
        / "countries.json"
    )

    summer_window = {
        "season_key": "summer",
        "start_month": 6,
        "start_day": 1,
        "end_month": 8,
        "end_day": 31,
    }

    config_path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "countries": [
                    {
                        "country_code": "SA",
                        "market_groups": [
                            "GCC",
                        ],
                        "hemisphere": (
                            "northern"
                        ),
                        "timezone": (
                            "Asia/Riyadh"
                        ),
                        "languages": [
                            "ar",
                        ],
                        "season_windows": [
                            summer_window,
                            summer_window,
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        CountryRegistryError,
        match="Duplicate season key",
    ):
        (
            CountryCreativeRegistry
            .from_json_file(
                config_path
            )
        )
