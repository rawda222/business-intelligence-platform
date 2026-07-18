"""
Market Moment Date Resolvers

Resolves configured market-moment date rules into concrete calendar
windows for one country and campaign date.

Supported rules:

- Country season.
- Fixed annual range.
- Hijri annual range.
- Country/year override.
- Explicit date range.

Country/year overrides take precedence over calculated rules.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from hijridate import Gregorian, Hijri

from app.creative_context.exceptions import (
    MomentDateOverrideError,
    MomentDateResolutionError,
)
from app.creative_context.schemas import (
    CountryCreativeProfile,
    MarketMomentDefinition,
    ResolvedMomentWindow,
)


DEFAULT_MOMENT_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "creative_context"
    / "moment_overrides.json"
)


# ============================================================
# Date Override
# ============================================================
class MomentDateOverride:
    """One country/year override for a market moment."""

    def __init__(
        self,
        *,
        country_code: str,
        moment_key: str,
        year: int,
        active_from: date,
        active_until: date,
        source: str,
        version: str = "1",
    ):
        normalized_country = (
            country_code.strip().upper()
        )

        normalized_key = (
            moment_key.strip().lower()
        )

        if (
            len(normalized_country) != 2
            or not normalized_country.isalpha()
        ):
            raise MomentDateOverrideError(
                "Override country_code must use "
                "ISO alpha-2 format."
            )

        if not normalized_key:
            raise MomentDateOverrideError(
                "Override moment_key cannot "
                "be empty."
            )

        if year < 1:
            raise MomentDateOverrideError(
                "Override year must be "
                "a positive integer."
            )

        if active_until < active_from:
            raise MomentDateOverrideError(
                "Override active_until must be "
                "on or after active_from."
            )

        if not source.strip():
            raise MomentDateOverrideError(
                "Override source cannot be empty."
            )

        if not version.strip():
            raise MomentDateOverrideError(
                "Override version cannot be empty."
            )

        self.country_code = (
            normalized_country
        )

        self.moment_key = normalized_key

        self.year = year

        self.active_from = active_from

        self.active_until = active_until

        self.source = source.strip()

        self.version = version.strip()


# ============================================================
# Date Override Registry
# ============================================================
class MomentDateOverrideRegistry:
    """Validated country/year date-override registry."""

    def __init__(
        self,
        *,
        registry_version: str,
        overrides: list[
            MomentDateOverride
        ],
    ):
        if not registry_version.strip():
            raise MomentDateOverrideError(
                "Override registry_version "
                "cannot be empty."
            )

        self.registry_version = (
            registry_version.strip()
        )

        self._overrides: dict[
            tuple[str, str, int],
            MomentDateOverride,
        ] = {}

        for override in overrides:
            key = (
                override.country_code,
                override.moment_key,
                override.year,
            )

            if key in self._overrides:
                raise MomentDateOverrideError(
                    "Duplicate moment date "
                    "override: "
                    f"{key}"
                )

            self._overrides[key] = override

    @classmethod
    def from_json_file(
        cls,
        path: Path,
    ) -> "MomentDateOverrideRegistry":
        """Load override configuration from JSON."""

        try:
            raw_text = path.read_text(
                encoding="utf-8",
            )
        except OSError as error:
            raise MomentDateOverrideError(
                "Could not read moment "
                f"overrides: {path}"
            ) from error

        try:
            payload = json.loads(
                raw_text
            )
        except json.JSONDecodeError as error:
            raise MomentDateOverrideError(
                "Moment overrides contain "
                "invalid JSON."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise MomentDateOverrideError(
                "Moment overrides root must "
                "be an object."
            )

        registry_version = payload.get(
            "registry_version"
        )

        raw_overrides = payload.get(
            "overrides"
        )

        if not isinstance(
            registry_version,
            str,
        ):
            raise MomentDateOverrideError(
                "Override registry_version "
                "must be a string."
            )

        if not isinstance(
            raw_overrides,
            list,
        ):
            raise MomentDateOverrideError(
                "overrides must be a list."
            )

        overrides: list[
            MomentDateOverride
        ] = []

        for item in raw_overrides:
            if not isinstance(
                item,
                dict,
            ):
                raise MomentDateOverrideError(
                    "Each override must be "
                    "an object."
                )

            try:
                override = (
                    MomentDateOverride(
                        country_code=str(
                            item[
                                "country_code"
                            ]
                        ),
                        moment_key=str(
                            item[
                                "moment_key"
                            ]
                        ),
                        year=int(
                            item["year"]
                        ),
                        active_from=(
                            date.fromisoformat(
                                str(
                                    item[
                                        "active_from"
                                    ]
                                )
                            )
                        ),
                        active_until=(
                            date.fromisoformat(
                                str(
                                    item[
                                        "active_until"
                                    ]
                                )
                            )
                        ),
                        source=str(
                            item["source"]
                        ),
                        version=str(
                            item.get(
                                "version",
                                "1",
                            )
                        ),
                    )
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                raise MomentDateOverrideError(
                    "Invalid moment override "
                    "definition."
                ) from error

            overrides.append(
                override
            )

        return cls(
            registry_version=(
                registry_version
            ),
            overrides=overrides,
        )

    def find(
        self,
        *,
        country_code: str,
        moment_key: str,
        year: int,
    ) -> MomentDateOverride | None:
        """Return an exact override when configured."""

        return self._overrides.get(
            (
                country_code.strip().upper(),
                moment_key.strip().lower(),
                year,
            )
        )


def load_default_moment_overrides(
) -> MomentDateOverrideRegistry:
    """Load production moment-date overrides."""

    return (
        MomentDateOverrideRegistry
        .from_json_file(
            DEFAULT_MOMENT_OVERRIDES_PATH
        )
    )


# ============================================================
# Shared Date Helpers
# ============================================================
def _build_annual_window(
    *,
    year: int,
    start_month: int,
    start_day: int,
    end_month: int,
    end_day: int,
) -> tuple[date, date]:
    """
    Build a fixed annual range.

    When the configured end month/day precedes the start month/day,
    the range is interpreted as crossing into the following year.
    """

    try:
        active_from = date(
            year,
            start_month,
            start_day,
        )
    except ValueError as error:
        raise MomentDateResolutionError(
            "Invalid fixed annual start date."
        ) from error

    end_year = year

    if (
        end_month,
        end_day,
    ) < (
        start_month,
        start_day,
    ):
        end_year += 1

    try:
        active_until = date(
            end_year,
            end_month,
            end_day,
        )
    except ValueError as error:
        raise MomentDateResolutionError(
            "Invalid fixed annual end date."
        ) from error

    return (
        active_from,
        active_until,
    )


def _distance_to_window(
    *,
    target: date,
    active_from: date,
    active_until: date,
) -> int:
    """Return day distance from a target date to an active window."""

    if target < active_from:
        return (
            active_from - target
        ).days

    if target > active_until:
        return (
            target - active_until
        ).days

    return 0


def _select_nearest_window(
    *,
    candidates: list[
        tuple[date, date]
    ],
    campaign_date: date,
) -> tuple[date, date]:
    """Select the candidate window nearest to the campaign date."""

    if not candidates:
        raise MomentDateResolutionError(
            "No candidate date windows "
            "were produced."
        )

    return min(
        candidates,
        key=lambda candidate: (
            _distance_to_window(
                target=campaign_date,
                active_from=candidate[0],
                active_until=candidate[1],
            ),
            abs(
                (
                    candidate[0]
                    - campaign_date
                ).days
            ),
        ),
    )


# ============================================================
# Country Season Resolution
# ============================================================
def _country_season_candidates(
    *,
    moment: MarketMomentDefinition,
    country: CountryCreativeProfile,
    campaign_date: date,
) -> list[
    tuple[date, date]
]:
    """Build nearby country-season windows."""

    season_key = (
        moment.date_rule.season_key
    )

    if season_key is None:
        raise MomentDateResolutionError(
            "Country-season rule does not "
            "define season_key."
        )

    season_window = next(
        (
            window
            for window in (
                country.season_windows
            )
            if (
                window.season_key
                == season_key
            )
        ),
        None,
    )

    if season_window is None:
        raise MomentDateResolutionError(
            "Country does not configure "
            f"season '{season_key}'."
        )

    return [
        _build_annual_window(
            year=year,
            start_month=(
                season_window.start_month
            ),
            start_day=(
                season_window.start_day
            ),
            end_month=(
                season_window.end_month
            ),
            end_day=(
                season_window.end_day
            ),
        )
        for year in (
            campaign_date.year - 1,
            campaign_date.year,
            campaign_date.year + 1,
        )
    ]


# ============================================================
# Fixed Annual Resolution
# ============================================================
def _fixed_annual_candidates(
    *,
    moment: MarketMomentDefinition,
    campaign_date: date,
) -> list[
    tuple[date, date]
]:
    """Build nearby fixed-calendar windows."""

    rule = moment.date_rule

    required_values = (
        rule.start_month,
        rule.start_day,
        rule.end_month,
        rule.end_day,
    )

    if any(
        value is None
        for value in required_values
    ):
        raise MomentDateResolutionError(
            "Fixed annual rule is incomplete."
        )

    start_month = rule.start_month
    start_day = rule.start_day
    end_month = rule.end_month
    end_day = rule.end_day

    if (
        start_month is None
        or start_day is None
        or end_month is None
        or end_day is None
    ):
        raise MomentDateResolutionError(
            "Fixed annual rule is incomplete."
        )

    return [
        _build_annual_window(
            year=year,
            start_month=start_month,
            start_day=start_day,
            end_month=end_month,
            end_day=end_day,
        )
        for year in (
            campaign_date.year - 1,
            campaign_date.year,
            campaign_date.year + 1,
        )
    ]


# ============================================================
# Hijri Resolution
# ============================================================
def _gregorian_date_from_hijri(
    *,
    year: int,
    month: int,
    day: int,
) -> date:
    """
    Convert a Hijri date to Gregorian.

    If the configured final day does not exist in a particular
    Hijri month, the latest valid day at or below it is used.
    """

    candidate_day = day

    while candidate_day >= 1:
        try:
            converted = Hijri(
                year,
                month,
                candidate_day,
            ).to_gregorian()

            return date(
                converted.year,
                converted.month,
                converted.day,
            )
        except ValueError:
            candidate_day -= 1

    raise MomentDateResolutionError(
        "Could not resolve configured "
        "Hijri date."
    )


def _hijri_candidates(
    *,
    moment: MarketMomentDefinition,
    campaign_date: date,
) -> list[
    tuple[date, date]
]:
    """Build nearby Hijri-calendar windows."""

    rule = moment.date_rule

    required_values = (
        rule.hijri_start_month,
        rule.hijri_start_day,
        rule.hijri_end_month,
        rule.hijri_end_day,
    )

    if any(
        value is None
        for value in required_values
    ):
        raise MomentDateResolutionError(
            "Hijri annual rule is incomplete."
        )

    start_month = (
        rule.hijri_start_month
    )
    start_day = (
        rule.hijri_start_day
    )
    end_month = (
        rule.hijri_end_month
    )
    end_day = (
        rule.hijri_end_day
    )

    if (
        start_month is None
        or start_day is None
        or end_month is None
        or end_day is None
    ):
        raise MomentDateResolutionError(
            "Hijri annual rule is incomplete."
        )

    january_hijri = Gregorian(
        campaign_date.year,
        1,
        1,
    ).to_hijri()

    december_hijri = Gregorian(
        campaign_date.year,
        12,
        31,
    ).to_hijri()

    first_hijri_year = min(
        january_hijri.year,
        december_hijri.year,
    )

    last_hijri_year = max(
        january_hijri.year,
        december_hijri.year,
    )

    candidates: list[
        tuple[date, date]
    ] = []

    for hijri_year in range(
        first_hijri_year - 1,
        last_hijri_year + 2,
    ):
        active_from = (
            _gregorian_date_from_hijri(
                year=hijri_year,
                month=start_month,
                day=start_day,
            )
        )

        end_hijri_year = hijri_year

        if (
            end_month,
            end_day,
        ) < (
            start_month,
            start_day,
        ):
            end_hijri_year += 1

        active_until = (
            _gregorian_date_from_hijri(
                year=end_hijri_year,
                month=end_month,
                day=end_day,
            )
        )

        candidates.append(
            (
                active_from,
                active_until,
            )
        )

    return candidates


# ============================================================
# Explicit Date Resolution
# ============================================================
def _explicit_candidates(
    *,
    moment: MarketMomentDefinition,
) -> list[
    tuple[date, date]
]:
    """Return one configured explicit window."""

    rule = moment.date_rule

    if (
        rule.explicit_start is None
        or rule.explicit_end is None
    ):
        raise MomentDateResolutionError(
            "Explicit date rule is incomplete."
        )

    return [
        (
            rule.explicit_start,
            rule.explicit_end,
        )
    ]


# ============================================================
# Status Resolution
# ============================================================
def _resolve_status(
    *,
    campaign_date: date,
    lead_from: date,
    active_from: date,
    active_until: date,
    cooldown_until: date,
) -> str:
    """Resolve campaign-date status against one full window."""

    if (
        active_from
        <= campaign_date
        <= active_until
    ):
        return "active"

    if (
        lead_from
        <= campaign_date
        < active_from
    ):
        return "upcoming"

    if (
        active_until
        < campaign_date
        <= cooldown_until
    ):
        return "cooldown"

    return "inactive"


# ============================================================
# Public Resolver
# ============================================================
def resolve_moment_window(
    *,
    moment: MarketMomentDefinition,
    country: CountryCreativeProfile,
    campaign_date: date,
    overrides: (
        MomentDateOverrideRegistry | None
    ) = None,
) -> ResolvedMomentWindow:
    """Resolve one concrete market-moment calendar window."""

    used_overrides = (
        overrides
        or load_default_moment_overrides()
    )

    override = used_overrides.find(
        country_code=(
            country.country_code
        ),
        moment_key=moment.key,
        year=campaign_date.year,
    )

    date_source = (
        moment.date_rule.rule_type
    )

    evidence_reference = (
        f"moment:{moment.key}:"
        f"{moment.version}"
    )

    if override is not None:
        active_from = (
            override.active_from
        )

        active_until = (
            override.active_until
        )

        date_source = (
            "country_year_override"
        )

        evidence_reference = (
            "moment-override:"
            f"{country.country_code}:"
            f"{moment.key}:"
            f"{override.year}:"
            f"{override.version}"
        )

    else:
        rule_type = (
            moment.date_rule.rule_type
        )

        if rule_type == "country_season":
            candidates = (
                _country_season_candidates(
                    moment=moment,
                    country=country,
                    campaign_date=(
                        campaign_date
                    ),
                )
            )

            evidence_reference = (
                "country-profile:"
                f"{country.country_code}:"
                f"{country.version}"
            )

        elif (
            rule_type
            == "fixed_annual_range"
        ):
            candidates = (
                _fixed_annual_candidates(
                    moment=moment,
                    campaign_date=(
                        campaign_date
                    ),
                )
            )

        elif (
            rule_type
            == "hijri_annual_range"
        ):
            candidates = (
                _hijri_candidates(
                    moment=moment,
                    campaign_date=(
                        campaign_date
                    ),
                )
            )

        elif (
            rule_type
            == "explicit_date_range"
        ):
            candidates = (
                _explicit_candidates(
                    moment=moment,
                )
            )

        elif (
            rule_type
            == "country_specific_date"
        ):
            raise MomentDateResolutionError(
                "Country-specific moment "
                f"'{moment.key}' requires a "
                "country/year override."
            )

        else:
            raise MomentDateResolutionError(
                "Unsupported date rule: "
                f"{rule_type}"
            )

        (
            active_from,
            active_until,
        ) = _select_nearest_window(
            candidates=candidates,
            campaign_date=campaign_date,
        )

    lead_from = (
        active_from
        - timedelta(
            days=moment.lead_days,
        )
    )

    cooldown_until = (
        active_until
        + timedelta(
            days=moment.cooldown_days,
        )
    )

    status = _resolve_status(
        campaign_date=campaign_date,
        lead_from=lead_from,
        active_from=active_from,
        active_until=active_until,
        cooldown_until=(
            cooldown_until
        ),
    )

    return ResolvedMomentWindow(
        moment_key=moment.key,
        country_code=(
            country.country_code
        ),
        campaign_date=campaign_date,
        active_from=active_from,
        active_until=active_until,
        lead_from=lead_from,
        cooldown_until=(
            cooldown_until
        ),
        status=status,
        date_source=date_source,
        evidence_reference=(
            evidence_reference
        ),
    )
