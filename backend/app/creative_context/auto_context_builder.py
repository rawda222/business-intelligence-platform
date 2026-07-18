"""
Automatic Campaign Context Builder

Builds the internal MomentResolutionRequest without asking the user
to provide campaign context.

Current sources:

- Business profile.
- Country creative registry.
- Connected social platforms.
- Explicit product policies.

Optional strategy and performance signals may override safe defaults
without changing the seasonal creative-context engine.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from app.creative_context.country_registry import (
    CountryCreativeRegistry,
    load_default_country_registry,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    MomentResolutionRequest,
)


ContextSource = Literal[
    "business_profile",
    "business_timezone_current_date",
    "connected_platform_policy",
    "platform_default_policy",
    "approved_strategy",
    "business_performance",
    "business_industry_fallback",
    "business_type_fallback",
    "default_policy",
]


@dataclass(frozen=True, slots=True)
class AutoContextField:
    """One automatically resolved field with provenance."""

    value: str

    source: ContextSource

    confidence: float


@dataclass(frozen=True, slots=True)
class AutoCreativeSignals:
    """
    Optional higher-priority signals.

    Future Strategy and Business Trend adapters may populate these
    fields without changing the automatic builder contract.
    """

    preferred_platform: str | None = None
    preferred_content_format: str | None = None
    objective: str | None = None
    product_context: str | None = None
    platform_source: ContextSource = (
        "business_performance"
    )
    format_source: ContextSource = (
        "business_performance"
    )
    objective_source: ContextSource = (
        "approved_strategy"
    )
    product_source: ContextSource = (
        "approved_strategy"
    )
    evidence_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AutomaticCampaignContext:
    """Internal request plus provenance for every resolved field."""

    request: MomentResolutionRequest

    campaign_date: AutoContextField

    target_country_code: AutoContextField

    platform: AutoContextField

    content_format: AutoContextField

    objective: AutoContextField

    product_context: AutoContextField

    evidence_references: tuple[str, ...] = ()

    warnings: tuple[str, ...] = ()


_PLATFORM_PRIORITY = (
    "instagram",
    "facebook",
)


_PLATFORM_DEFAULT_FORMATS = {
    "instagram": "feed_post",
    "facebook": "feed_post",
}


def _clean_platforms(
    platforms: list[str],
) -> list[str]:
    """Normalize and deduplicate connected platforms."""

    normalized: list[str] = []

    for platform in platforms:
        cleaned = (
            platform.strip().lower()
        )

        if (
            cleaned
            and cleaned not in normalized
        ):
            normalized.append(
                cleaned
            )

    return normalized


def _select_connected_platform(
    platforms: list[str],
) -> str:
    """Select a connected platform using deterministic policy."""

    normalized = _clean_platforms(
        platforms
    )

    for preferred in _PLATFORM_PRIORITY:
        if preferred in normalized:
            return preferred

    if normalized:
        return sorted(
            normalized
        )[0]

    return "instagram"


def _default_format_for_platform(
    platform: str,
) -> str:
    """Return the configured safe format for one platform."""

    return _PLATFORM_DEFAULT_FORMATS.get(
        platform,
        "feed_post",
    )


def build_automatic_campaign_context(
    *,
    business: BusinessCreativeContext,
    connected_platforms: list[str],
    signals: AutoCreativeSignals | None = None,
    country_registry: (
        CountryCreativeRegistry | None
    ) = None,
    current_time: datetime | None = None,
) -> AutomaticCampaignContext:
    """Build the internal automatic campaign request."""

    used_registry = (
        country_registry
        or load_default_country_registry()
    )

    country = used_registry.get(
        business.country_code
    )

    used_time = (
        current_time
        or datetime.now(
            UTC
        )
    )

    if used_time.tzinfo is None:
        used_time = used_time.replace(
            tzinfo=UTC
        )

    local_date = used_time.astimezone(
        ZoneInfo(
            country.timezone
        )
    ).date()

    used_signals = (
        signals
        or AutoCreativeSignals()
    )

    connected = _clean_platforms(
        connected_platforms
    )

    warnings: list[str] = []

    if used_signals.preferred_platform:
        platform = (
            used_signals
            .preferred_platform
            .strip()
            .lower()
        )

        platform_source = (
            used_signals.platform_source
        )

        platform_confidence = 0.85
    else:
        platform = (
            _select_connected_platform(
                connected
            )
        )

        platform_source = (
            "connected_platform_policy"
        )

        platform_confidence = (
            0.75
            if connected
            else 0.40
        )

        if not connected:
            warnings.append(
                "No active connected social "
                "platform was available; "
                "the default visual platform "
                "policy was used."
            )

    if (
        used_signals
        .preferred_content_format
    ):
        content_format = (
            used_signals
            .preferred_content_format
            .strip()
            .lower()
        )

        format_source = (
            used_signals.format_source
        )

        format_confidence = 0.80
    else:
        content_format = (
            _default_format_for_platform(
                platform
            )
        )

        format_source = (
            "platform_default_policy"
        )

        format_confidence = 0.60

    if used_signals.objective:
        objective = (
            used_signals.objective
            .strip()
            .lower()
        )

        objective_source = (
            used_signals.objective_source
        )

        objective_confidence = 0.85
    else:
        objective = "awareness"

        objective_source = (
            "default_policy"
        )

        objective_confidence = 0.60

    if used_signals.product_context:
        product_context = (
            used_signals
            .product_context
            .strip()
        )

        product_source = (
            used_signals.product_source
        )

        product_confidence = 0.80
    elif business.industry:
        product_context = (
            business.industry
        )

        product_source = (
            "business_industry_fallback"
        )

        product_confidence = 0.60
    else:
        product_context = (
            business.business_type
        )

        product_source = (
            "business_type_fallback"
        )

        product_confidence = 0.50

    request = MomentResolutionRequest(
        campaign_date=local_date,
        target_country_code=(
            country.country_code
        ),
        platform=platform,
        content_format=content_format,
        objective=objective,
        product_context=product_context,
        selection_mode="automatic",
    )

    return AutomaticCampaignContext(
        request=request,
        campaign_date=AutoContextField(
            value=local_date.isoformat(),
            source=(
                "business_timezone_current_date"
            ),
            confidence=1.0,
        ),
        target_country_code=(
            AutoContextField(
                value=country.country_code,
                source="business_profile",
                confidence=1.0,
            )
        ),
        platform=AutoContextField(
            value=platform,
            source=platform_source,
            confidence=(
                platform_confidence
            ),
        ),
        content_format=AutoContextField(
            value=content_format,
            source=format_source,
            confidence=format_confidence,
        ),
        objective=AutoContextField(
            value=objective,
            source=objective_source,
            confidence=objective_confidence,
        ),
        product_context=AutoContextField(
            value=product_context,
            source=product_source,
            confidence=product_confidence,
        ),
        evidence_references=(
            used_signals
            .evidence_references
        ),
        warnings=tuple(
            warnings
        ),
    )