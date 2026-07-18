"""
Seasonal Creative Context Contracts

Defines the stable, versioned contracts shared between:

- Market moment registry.
- Country and region registry.
- Moment date resolvers.
- Business eligibility resolver.
- Theme selector.
- Creative theme brief builder.
- Image generation consumers.

This module contains no calendar calculations, database access,
LLM calls, or image-generation logic.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# Contract Constants
# ============================================================
CREATIVE_THEME_CONTRACT_VERSION = "1.0"


# ============================================================
# Common Types
# ============================================================
MomentType = Literal[
    "season",
    "religious",
    "national",
    "commercial",
    "education",
    "cultural",
]


DateRuleType = Literal[
    "country_season",
    "fixed_annual_range",
    "hijri_annual_range",
    "country_specific_date",
    "explicit_date_range",
]


MomentStatus = Literal[
    "upcoming",
    "active",
    "cooldown",
    "inactive",
]

DateResolutionSource = Literal[
    "country_season",
    "fixed_annual_range",
    "hijri_annual_range",
    "country_specific_date",
    "explicit_date_range",
    "country_year_override",
]

BusinessFitLevel = Literal[
    "high",
    "medium",
    "low",
    "not_applicable",
]


SelectionMode = Literal[
    "automatic",
    "user_override",
    "brand_only",
]


MomentSelectionState = Literal[
    "selected",
    "secondary",
    "rejected",
]


Hemisphere = Literal[
    "northern",
    "southern",
    "equatorial",
]


# ============================================================
# Base Contract Model
# ============================================================
class CreativeContextModel(
    BaseModel
):
    """Base model for creative-context contracts."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator(
        "evidence_references",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def deduplicate_evidence_references(
        cls,
        value: object,
    ) -> object:
        """
        Remove duplicate evidence references while preserving order.

        The validator is inherited by creative-context models that
        define an evidence_references field.
        """

        if value is None:
            return value

        if not isinstance(
            value,
            (list, tuple),
        ):
            return value

        result: list[object] = []

        for item in value:
            if not isinstance(
                item,
                str,
            ):
                if item not in result:
                    result.append(item)

                continue

            cleaned = item.strip()

            if (
                cleaned
                and cleaned not in result
            ):
                result.append(cleaned)

        return result


# ============================================================
# Country and Region Contracts
# ============================================================
class CountrySeasonWindow(
    CreativeContextModel
):
    """Configured season window for one country."""

    season_key: str = Field(
        min_length=1,
        max_length=50,
    )

    start_month: int = Field(
        ge=1,
        le=12,
    )

    start_day: int = Field(
        ge=1,
        le=31,
    )

    end_month: int = Field(
        ge=1,
        le=12,
    )

    end_day: int = Field(
        ge=1,
        le=31,
    )


class CountryCreativeProfile(
    CreativeContextModel
):
    """Creative-market configuration for one country."""

    country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    market_groups: list[str] = Field(
        default_factory=list,
    )

    hemisphere: Hemisphere

    timezone: str = Field(
        min_length=1,
        max_length=100,
    )

    languages: list[str] = Field(
        min_length=1,
    )

    season_windows: list[
        CountrySeasonWindow
    ] = Field(
        default_factory=list,
    )

    enabled: bool = True

    version: str = Field(
        default="1",
        min_length=1,
        max_length=30,
    )

    @field_validator(
        "market_groups",
        "languages",
    )
    @classmethod
    def normalize_unique_values(
        cls,
        values: list[str],
    ) -> list[str]:
        """Normalize and preserve unique ordered values."""

        normalized: list[str] = []

        for value in values:
            cleaned = value.strip()

            if (
                cleaned
                and cleaned not in normalized
            ):
                normalized.append(
                    cleaned
                )

        return normalized


# ============================================================
# Moment Date Rules
# ============================================================
class MomentDateRule(
    CreativeContextModel
):
    """Rule used to resolve a moment's date window."""

    rule_type: DateRuleType

    season_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    start_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    start_day: int | None = Field(
        default=None,
        ge=1,
        le=31,
    )

    end_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    end_day: int | None = Field(
        default=None,
        ge=1,
        le=31,
    )

    hijri_start_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    hijri_start_day: int | None = Field(
        default=None,
        ge=1,
        le=30,
    )

    hijri_end_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    hijri_end_day: int | None = Field(
        default=None,
        ge=1,
        le=30,
    )

    explicit_start: date | None = None

    explicit_end: date | None = None

    country_event_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_rule_configuration(
        self,
    ) -> "MomentDateRule":
        """Ensure required fields exist for the selected rule."""

        if self.rule_type == "country_season":
            if self.season_key is None:
                raise ValueError(
                    "country_season requires "
                    "season_key."
                )

        elif (
            self.rule_type
            == "fixed_annual_range"
        ):
            required_values = (
                self.start_month,
                self.start_day,
                self.end_month,
                self.end_day,
            )

            if any(
                value is None
                for value in required_values
            ):
                raise ValueError(
                    "fixed_annual_range requires "
                    "start_month, start_day, "
                    "end_month, and end_day."
                )

        elif (
            self.rule_type
            == "hijri_annual_range"
        ):
            required_values = (
                self.hijri_start_month,
                self.hijri_start_day,
                self.hijri_end_month,
                self.hijri_end_day,
            )

            if any(
                value is None
                for value in required_values
            ):
                raise ValueError(
                    "hijri_annual_range requires "
                    "all Hijri start and end "
                    "fields."
                )

        elif (
            self.rule_type
            == "country_specific_date"
        ):
            if self.country_event_key is None:
                raise ValueError(
                    "country_specific_date "
                    "requires country_event_key."
                )

        elif (
            self.rule_type
            == "explicit_date_range"
        ):
            if (
                self.explicit_start is None
                or self.explicit_end is None
            ):
                raise ValueError(
                    "explicit_date_range requires "
                    "explicit_start and "
                    "explicit_end."
                )

            if (
                self.explicit_end
                < self.explicit_start
            ):
                raise ValueError(
                    "explicit_end must be on or "
                    "after explicit_start."
                )

        return self


# ============================================================
# Market Moment Definition
# ============================================================
class MarketMomentDefinition(
    CreativeContextModel
):
    """One versioned market-moment definition."""

    key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_]+$",
    )

    display_name: str = Field(
        min_length=1,
        max_length=150,
    )

    moment_type: MomentType

    date_rule: MomentDateRule

    applicable_countries: list[str] = Field(
        default_factory=list,
    )

    applicable_market_groups: list[str] = Field(
        default_factory=list,
    )

    high_fit_business_types: list[str] = Field(
        default_factory=list,
    )

    medium_fit_business_types: list[str] = Field(
        default_factory=list,
    )

    low_fit_business_types: list[str] = Field(
        default_factory=list,
    )

    excluded_business_types: list[str] = Field(
        default_factory=list,
    )

    applicable_objectives: list[str] = Field(
        default_factory=list,
    )

    lead_days: int = Field(
        default=0,
        ge=0,
        le=365,
    )

    cooldown_days: int = Field(
        default=0,
        ge=0,
        le=180,
    )

    priority: int = Field(
        default=50,
        ge=0,
        le=100,
    )

    visual_tokens: list[str] = Field(
        default_factory=list,
    )

    default_avoid_elements: list[str] = Field(
        default_factory=list,
    )

    enabled: bool = True

    version: str = Field(
        default="1",
        min_length=1,
        max_length=30,
    )

    @field_validator(
        "applicable_countries",
    )
    @classmethod
    def validate_country_codes(
        cls,
        values: list[str],
    ) -> list[str]:
        """Normalize and validate ISO alpha-2 country codes."""

        normalized: list[str] = []

        for value in values:
            country_code = (
                value.strip().upper()
            )

            if (
                len(country_code) != 2
                or not country_code.isalpha()
            ):
                raise ValueError(
                    "Country codes must use "
                    "ISO alpha-2 format."
                )

            if country_code not in normalized:
                normalized.append(
                    country_code
                )

        return normalized

    @model_validator(mode="after")
    def validate_business_fit_groups(
        self,
    ) -> "MarketMomentDefinition":
        """Reject business types assigned to conflicting groups."""

        fit_groups = {
            "high": set(
                self.high_fit_business_types
            ),
            "medium": set(
                self.medium_fit_business_types
            ),
            "low": set(
                self.low_fit_business_types
            ),
            "excluded": set(
                self.excluded_business_types
            ),
        }

        group_names = list(
            fit_groups.keys()
        )

        for index, first_name in enumerate(
            group_names
        ):
            for second_name in group_names[
                index + 1:
            ]:
                overlap = (
                    fit_groups[first_name]
                    & fit_groups[second_name]
                )

                if overlap:
                    raise ValueError(
                        "Business types cannot "
                        "appear in multiple fit "
                        "groups: "
                        f"{sorted(overlap)}"
                    )

        return self


# ============================================================
# Resolution Request
# ============================================================
class MomentResolutionRequest(
    CreativeContextModel
):
    """Request used to resolve a creative market moment."""

    campaign_date: date

    target_country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    platform: str = Field(
        min_length=1,
        max_length=50,
    )

    content_format: str = Field(
        min_length=1,
        max_length=50,
    )

    objective: str = Field(
        min_length=1,
        max_length=100,
    )

    product_context: str | None = Field(
        default=None,
        max_length=500,
    )

    selection_mode: SelectionMode = (
        "automatic"
    )

    moment_override: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_]+$",
    )

    @model_validator(mode="after")
    def validate_selection_mode(
        self,
    ) -> "MomentResolutionRequest":
        """Require an override key only in override mode."""

        if (
            self.selection_mode
            == "user_override"
            and self.moment_override is None
        ):
            raise ValueError(
                "user_override selection mode "
                "requires moment_override."
            )

        if (
            self.selection_mode
            != "user_override"
            and self.moment_override is not None
        ):
            raise ValueError(
                "moment_override is only valid "
                "when selection_mode is "
                "user_override."
            )

        return self


class BusinessCreativeContext(
    CreativeContextModel
):
    """Minimized business context used by the resolver."""

    business_id: UUID

    business_type: str = Field(
        min_length=1,
        max_length=100,
    )

    industry: str | None = Field(
        default=None,
        max_length=150,
    )

    country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    location: str | None = Field(
        default=None,
        max_length=200,
    )

    brand_rules: list[str] = Field(
        default_factory=list,
    )

    business_metadata: dict[
        str,
        str | int | float | bool | None,
    ] = Field(
        default_factory=dict,
    )


# ============================================================
# Resolved Moment Contracts
# ============================================================
class ResolvedMomentWindow(
    CreativeContextModel
):
    """Resolved calendar window for one market moment."""

    moment_key: str = Field(
        min_length=1,
        max_length=100,
    )

    country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    campaign_date: date

    active_from: date

    active_until: date

    lead_from: date

    cooldown_until: date

    status: MomentStatus

    date_source: DateResolutionSource

    evidence_reference: str = Field(
        min_length=1,
        max_length=300,
    )

    @model_validator(mode="after")
    def validate_window_order(
        self,
    ) -> "ResolvedMomentWindow":
        """Validate lead, active, and cooldown ordering."""

        if self.active_until < self.active_from:
            raise ValueError(
                "active_until must be on or "
                "after active_from."
            )

        if self.lead_from > self.active_from:
            raise ValueError(
                "lead_from must be on or "
                "before active_from."
            )

        if self.cooldown_until < self.active_until:
            raise ValueError(
                "cooldown_until must be on or "
                "after active_until."
            )

        return self


class ResolvedMarketMoment(
    CreativeContextModel
):
    """One resolved market moment for a concrete request."""

    key: str

    display_name: str

    moment_type: MomentType

    campaign_date: date

    active_from: date

    active_until: date

    status: MomentStatus

    business_fit: BusinessFitLevel

    eligible: bool

    priority: int = Field(
        ge=0,
        le=100,
    )

    selection_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    visual_tokens: list[str] = Field(
        default_factory=list,
    )

    avoid_elements: list[str] = Field(
        default_factory=list,
    )

    reasons: list[str] = Field(
        default_factory=list,
    )

    evidence_references: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_resolved_window(
        self,
    ) -> "ResolvedMarketMoment":
        """Ensure the resolved active window is valid."""

        if self.active_until < self.active_from:
            raise ValueError(
                "active_until must be on or "
                "after active_from."
            )

        if (
            self.business_fit
            == "not_applicable"
            and self.eligible
        ):
            raise ValueError(
                "A not_applicable moment "
                "cannot be eligible."
            )

        return self


class RejectedMarketMoment(
    CreativeContextModel
):
    """Moment considered but not selected."""

    key: str

    display_name: str

    status: MomentStatus

    business_fit: BusinessFitLevel

    reason: str = Field(
        min_length=1,
    )


# ============================================================
# Creative Theme Brief Contracts
# ============================================================
class CreativeDirection(
    CreativeContextModel
):
    """Model-independent visual direction."""

    concept: str = Field(
        min_length=1,
        max_length=500,
    )

    mood_keywords: list[str] = Field(
        default_factory=list,
    )

    visual_tokens: list[str] = Field(
        default_factory=list,
    )

    palette_hints: list[str] = Field(
        default_factory=list,
    )

    lighting_hint: str | None = Field(
        default=None,
        max_length=200,
    )

    composition_hint: str | None = Field(
        default=None,
        max_length=300,
    )


class CreativeConstraints(
    CreativeContextModel
):
    """Brand, market, and safety constraints for image generation."""

    brand_rules: list[str] = Field(
        default_factory=list,
    )

    market_rules: list[str] = Field(
        default_factory=list,
    )

    avoid_elements: list[str] = Field(
        default_factory=list,
    )


class CreativeThemeBrief(
    CreativeContextModel
):
    """Stable handoff contract for the image-generation team."""

    theme_key: str

    display_name: str

    source_moment: str

    moment_type: MomentType

    status: MomentStatus

    target_country_code: str = Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    market_groups: list[str] = Field(
        default_factory=list,
    )

    campaign_date: date

    platform: str

    content_format: str

    objective: str

    business_fit: BusinessFitLevel

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    valid_from: date

    valid_until: date

    creative_direction: CreativeDirection

    constraints: CreativeConstraints

    reasons: list[str] = Field(
        default_factory=list,
    )

    evidence_references: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_theme_validity(
        self,
    ) -> "CreativeThemeBrief":
        """Ensure the brief validity window is ordered."""

        if self.valid_until < self.valid_from:
            raise ValueError(
                "valid_until must be on or "
                "after valid_from."
            )

        return self


class ThemeFallback(
    CreativeContextModel
):
    """Fallback returned when no moment should be applied."""

    allowed: bool = True

    theme_key: str = "brand_only"

    reason: str = Field(
        min_length=1,
    )


class ThemeResolutionResult(
    CreativeContextModel
):
    """Final versioned result returned to image-generation clients."""

    contract_version: str = Field(
        default=(
            CREATIVE_THEME_CONTRACT_VERSION
        ),
    )

    registry_version: str = Field(
        min_length=1,
        max_length=50,
    )

    resolution_id: UUID

    generated_at: datetime

    business_id: UUID

    request: MomentResolutionRequest

    primary_theme: (
        CreativeThemeBrief | None
    ) = None

    secondary_accents: list[
        CreativeThemeBrief
    ] = Field(
        default_factory=list,
    )

    resolved_moments: list[
        ResolvedMarketMoment
    ] = Field(
        default_factory=list,
    )

    rejected_moments: list[
        RejectedMarketMoment
    ] = Field(
        default_factory=list,
    )

    fallback: ThemeFallback

    warnings: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_final_selection(
        self,
    ) -> "ThemeResolutionResult":
        """Ensure a result always has a usable outcome."""

        if (
            self.primary_theme is None
            and not self.fallback.allowed
        ):
            raise ValueError(
                "A result without a primary "
                "theme must allow fallback."
            )

        return self
class AutoContextFieldResponse(
    CreativeContextModel
):
    """One automatically inferred field with provenance."""

    value: str = Field(
        min_length=1,
        max_length=500,
    )

    source: str = Field(
        min_length=1,
        max_length=100,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class AutomaticCampaignContextResponse(
    CreativeContextModel
):
    """Public explanation of the generated campaign context."""

    request: MomentResolutionRequest

    campaign_date: AutoContextFieldResponse

    target_country_code: AutoContextFieldResponse

    platform: AutoContextFieldResponse

    content_format: AutoContextFieldResponse

    objective: AutoContextFieldResponse

    product_context: AutoContextFieldResponse

    evidence_references: list[str] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )


class SocialPlatformContextResponse(
    CreativeContextModel
):
    """Public summary of usable social platforms."""

    platforms: list[str] = Field(
        default_factory=list,
    )

    usable_account_ids: list[UUID] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )


class AutomaticCreativeThemeResponse(
    CreativeContextModel
):
    """Complete automatic creative-theme API response."""

    theme_result: ThemeResolutionResult

    automatic_context: (
        AutomaticCampaignContextResponse
    )

    social_platform_context: (
        SocialPlatformContextResponse
    )
class ImageGenerationHandoff(
    CreativeContextModel
):
    """
    Compact contract consumed by image-generation services.

    Internal resolution candidates, rejected moments, and social
    account details are intentionally excluded.
    """

    contract_version: str = Field(
        default="1.0",
        pattern=r"^1\.0$",
    )

    business_id: UUID

    resolution_id: UUID

    generated_at: datetime

    campaign_date: date

    target_country_code: str = Field(
        min_length=2,
        max_length=2,
    )

    platform: str = Field(
        min_length=1,
        max_length=50,
    )

    content_format: str = Field(
        min_length=1,
        max_length=100,
    )

    objective: str = Field(
        min_length=1,
        max_length=100,
    )

    product_context: str | None = Field(
        default=None,
        max_length=500,
    )

    theme: CreativeThemeBrief | None = None

    fallback: ThemeFallback

    evidence_references: list[str] = Field(
        default_factory=list,
    )