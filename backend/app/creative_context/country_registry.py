"""
Country Creative Registry

Loads, validates, and exposes country-level creative configuration.

Country records are loaded from versioned JSON configuration so
new countries and season windows can be introduced without changing
the resolver or the image-generation contract.
"""

import json
from pathlib import Path
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from pydantic import ValidationError

from app.creative_context.exceptions import (
    CountryNotFoundError,
    CountryRegistryError,
    DuplicateCountryCodeError,
)
from app.creative_context.schemas import (
    CountryCreativeProfile,
)


DEFAULT_COUNTRY_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "creative_context"
    / "countries.json"
)


class CountryCreativeRegistry:
    """Validated in-memory country creative registry."""

    def __init__(
        self,
        *,
        registry_version: str,
        profiles: list[
            CountryCreativeProfile
        ],
    ):
        if not registry_version.strip():
            raise CountryRegistryError(
                "registry_version cannot be empty."
            )

        self.registry_version = (
            registry_version.strip()
        )

        self._profiles: dict[
            str,
            CountryCreativeProfile,
        ] = {}

        for profile in profiles:
            country_code = (
                profile.country_code
            )

            if country_code in self._profiles:
                raise DuplicateCountryCodeError(
                    "Duplicate country code: "
                    f"{country_code}"
                )

            self._validate_profile(
                profile
            )

            self._profiles[
                country_code
            ] = profile

        if not self._profiles:
            raise CountryRegistryError(
                "Country registry cannot be empty."
            )

    @staticmethod
    def _validate_profile(
        profile: CountryCreativeProfile,
    ) -> None:
        """Validate timezone and unique season keys."""

        try:
            ZoneInfo(
                profile.timezone
            )
        except ZoneInfoNotFoundError as error:
            raise CountryRegistryError(
                "Unknown timezone "
                f"'{profile.timezone}' for "
                f"{profile.country_code}."
            ) from error

        season_keys = [
            window.season_key
            for window in (
                profile.season_windows
            )
        ]

        if (
            len(season_keys)
            != len(set(season_keys))
        ):
            raise CountryRegistryError(
                "Duplicate season key for "
                f"{profile.country_code}."
            )

    @classmethod
    def from_json_file(
        cls,
        path: Path,
    ) -> "CountryCreativeRegistry":
        """Load and validate a country registry JSON file."""

        try:
            raw_text = path.read_text(
                encoding="utf-8",
            )
        except OSError as error:
            raise CountryRegistryError(
                "Could not read country "
                f"registry: {path}"
            ) from error

        try:
            payload = json.loads(
                raw_text
            )
        except json.JSONDecodeError as error:
            raise CountryRegistryError(
                "Country registry contains "
                "invalid JSON."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise CountryRegistryError(
                "Country registry root must "
                "be an object."
            )

        registry_version = payload.get(
            "registry_version"
        )

        raw_countries = payload.get(
            "countries"
        )

        if not isinstance(
            registry_version,
            str,
        ):
            raise CountryRegistryError(
                "registry_version must be "
                "a string."
            )

        if not isinstance(
            raw_countries,
            list,
        ):
            raise CountryRegistryError(
                "countries must be a list."
            )

        try:
            profiles = [
                CountryCreativeProfile
                .model_validate(item)
                for item in raw_countries
            ]
        except ValidationError as error:
            raise CountryRegistryError(
                "Country registry profile "
                "validation failed."
            ) from error

        return cls(
            registry_version=(
                registry_version
            ),
            profiles=profiles,
        )

    def get(
        self,
        country_code: str,
    ) -> CountryCreativeProfile:
        """Return an enabled country profile."""

        normalized_code = (
            country_code.strip().upper()
        )

        profile = self._profiles.get(
            normalized_code
        )

        if (
            profile is None
            or not profile.enabled
        ):
            raise CountryNotFoundError(
                "Country is not configured "
                "or is disabled: "
                f"{normalized_code}"
            )

        return profile

    def list_enabled(
        self,
    ) -> list[
        CountryCreativeProfile
    ]:
        """Return enabled profiles ordered by country code."""

        return [
            self._profiles[
                country_code
            ]
            for country_code in sorted(
                self._profiles
            )
            if self._profiles[
                country_code
            ].enabled
        ]

    def contains(
        self,
        country_code: str,
    ) -> bool:
        """Return whether an enabled country exists."""

        try:
            self.get(
                country_code
            )
        except CountryNotFoundError:
            return False

        return True


def load_default_country_registry(
) -> CountryCreativeRegistry:
    """Load the production country configuration."""

    return (
        CountryCreativeRegistry
        .from_json_file(
            DEFAULT_COUNTRY_REGISTRY_PATH
        )
    )