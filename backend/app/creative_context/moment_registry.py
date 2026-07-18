"""
Market Moment Registry

Loads and validates versioned market-moment configuration.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.creative_context.exceptions import (
    DuplicateMomentKeyError,
    MomentNotFoundError,
    MomentRegistryError,
)
from app.creative_context.schemas import (
    MarketMomentDefinition,
)


DEFAULT_MOMENT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "creative_context"
    / "moments.json"
)


class MarketMomentRegistry:
    """Validated in-memory market-moment registry."""

    def __init__(
        self,
        *,
        registry_version: str,
        moments: list[
            MarketMomentDefinition
        ],
    ):
        if not registry_version.strip():
            raise MomentRegistryError(
                "registry_version cannot be empty."
            )

        self.registry_version = (
            registry_version.strip()
        )

        self._moments: dict[
            str,
            MarketMomentDefinition,
        ] = {}

        for moment in moments:
            if moment.key in self._moments:
                raise DuplicateMomentKeyError(
                    "Duplicate moment key: "
                    f"{moment.key}"
                )

            self._moments[
                moment.key
            ] = moment

        if not self._moments:
            raise MomentRegistryError(
                "Moment registry cannot be empty."
            )

    @classmethod
    def from_json_file(
        cls,
        path: Path,
    ) -> "MarketMomentRegistry":
        """Load and validate a moment registry JSON file."""

        try:
            raw_text = path.read_text(
                encoding="utf-8",
            )
        except OSError as error:
            raise MomentRegistryError(
                "Could not read moment "
                f"registry: {path}"
            ) from error

        try:
            payload = json.loads(
                raw_text
            )
        except json.JSONDecodeError as error:
            raise MomentRegistryError(
                "Moment registry contains "
                "invalid JSON."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise MomentRegistryError(
                "Moment registry root must "
                "be an object."
            )

        registry_version = payload.get(
            "registry_version"
        )

        raw_moments = payload.get(
            "moments"
        )

        if not isinstance(
            registry_version,
            str,
        ):
            raise MomentRegistryError(
                "registry_version must be "
                "a string."
            )

        if not isinstance(
            raw_moments,
            list,
        ):
            raise MomentRegistryError(
                "moments must be a list."
            )

        try:
            moments = [
                MarketMomentDefinition
                .model_validate(item)
                for item in raw_moments
            ]
        except ValidationError as error:
            raise MomentRegistryError(
                "Moment registry definition "
                "validation failed."
            ) from error

        return cls(
            registry_version=(
                registry_version
            ),
            moments=moments,
        )

    def get(
        self,
        moment_key: str,
    ) -> MarketMomentDefinition:
        """Return one enabled moment definition."""

        normalized_key = (
            moment_key.strip().lower()
        )

        moment = self._moments.get(
            normalized_key
        )

        if (
            moment is None
            or not moment.enabled
        ):
            raise MomentNotFoundError(
                "Moment is not configured "
                "or is disabled: "
                f"{normalized_key}"
            )

        return moment

    def list_enabled(
        self,
    ) -> list[
        MarketMomentDefinition
    ]:
        """Return enabled moments ordered by key."""

        return [
            self._moments[key]
            for key in sorted(
                self._moments
            )
            if self._moments[
                key
            ].enabled
        ]

    def contains(
        self,
        moment_key: str,
    ) -> bool:
        """Return whether an enabled moment exists."""

        try:
            self.get(
                moment_key
            )
        except MomentNotFoundError:
            return False

        return True


def load_default_moment_registry(
) -> MarketMomentRegistry:
    """Load the production market-moment configuration."""

    return (
        MarketMomentRegistry
        .from_json_file(
            DEFAULT_MOMENT_REGISTRY_PATH
        )
    )