"""
Automatic Creative Theme Service

Orchestrates business data, connected social accounts, automatic
campaign context, seasonal resolution, theme selection, and final
image-team brief construction.

The service does not query databases and does not call image models.
Database access remains the responsibility of the API/application
boundary.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from app.creative_context.auto_context_builder import (
    AutoCreativeSignals,
    AutomaticCampaignContext,
    build_automatic_campaign_context,
)
from app.creative_context.business_context_mapper import (
    map_business_to_creative_context,
)
from app.creative_context.country_registry import (
    CountryCreativeRegistry,
    load_default_country_registry,
)
from app.creative_context.date_resolvers import (
    MomentDateOverrideRegistry,
    load_default_moment_overrides,
)
from app.creative_context.moment_registry import (
    MarketMomentRegistry,
    load_default_moment_registry,
)
from app.creative_context.moment_resolver import (
    resolve_market_moments,
)
from app.creative_context.schemas import (
    ThemeResolutionResult,
)
from app.creative_context.social_platform_adapter import (
    ConnectedSocialPlatformContext,
    extract_connected_social_platforms,
)
from app.creative_context.theme_brief_builder import (
    build_theme_resolution_result,
)
from app.creative_context.theme_selector import (
    select_theme_moments,
)
from app.models.pg.business import Business
from app.models.pg.social_account import SocialAccount


@dataclass(frozen=True, slots=True)
class AutomaticCreativeThemeResult:
    """Final theme result plus automatic-decision provenance."""

    theme_result: ThemeResolutionResult
    automatic_context: AutomaticCampaignContext
    social_platform_context: ConnectedSocialPlatformContext


def _build_registry_version(
    *,
    country_registry: CountryCreativeRegistry,
    moment_registry: MarketMomentRegistry,
    override_registry: MomentDateOverrideRegistry,
) -> str:
    """Build one traceable combined registry version."""

    return (
        f"countries:{country_registry.registry_version};"
        f"moments:{moment_registry.registry_version};"
        f"overrides:{override_registry.registry_version}"
    )


def resolve_automatic_creative_theme(
    *,
    business: Business,
    social_accounts: Sequence[SocialAccount],
    signals: AutoCreativeSignals | None = None,
    country_registry: CountryCreativeRegistry | None = None,
    moment_registry: MarketMomentRegistry | None = None,
    overrides: MomentDateOverrideRegistry | None = None,
    current_time: datetime | None = None,
    max_secondary_moments: int = 1,
    resolution_id: UUID | None = None,
    generated_at: datetime | None = None,
) -> AutomaticCreativeThemeResult:
    """Resolve one complete automatic creative-theme contract."""

    used_country_registry = (
        country_registry or load_default_country_registry()
    )

    used_moment_registry = (
        moment_registry or load_default_moment_registry()
    )

    used_overrides = (
        overrides or load_default_moment_overrides()
    )

    business_context = map_business_to_creative_context(
        business
    )

    social_context = extract_connected_social_platforms(
        accounts=social_accounts,
        business_id=business.id,
    )

    automatic_context = build_automatic_campaign_context(
        business=business_context,
        connected_platforms=list(
            social_context.platforms
        ),
        signals=signals,
        country_registry=used_country_registry,
        current_time=current_time,
    )

    collection = resolve_market_moments(
        request=automatic_context.request,
        business=business_context,
        country_registry=used_country_registry,
        moment_registry=used_moment_registry,
        overrides=used_overrides,
    )

    decision = select_theme_moments(
        request=automatic_context.request,
        collection=collection,
        max_secondary_moments=max_secondary_moments,
    )

    combined_warnings = tuple(
        dict.fromkeys(
            [
                *collection.warnings,
                *automatic_context.warnings,
                *social_context.warnings,
            ]
        )
    )

    collection = type(collection)(
        resolved_moments=collection.resolved_moments,
        rejected_moments=collection.rejected_moments,
        warnings=combined_warnings,
    )

    theme_result = build_theme_resolution_result(
        request=automatic_context.request,
        business=business_context,
        collection=collection,
        decision=decision,
        registry_version=_build_registry_version(
            country_registry=used_country_registry,
            moment_registry=used_moment_registry,
            override_registry=used_overrides,
        ),
        country_registry=used_country_registry,
        resolution_id=resolution_id,
        generated_at=generated_at,
    )

    return AutomaticCreativeThemeResult(
        theme_result=theme_result,
        automatic_context=automatic_context,
        social_platform_context=social_context,
    )