"""
Creative Theme Brief Builder

Transforms a deterministic theme-selection decision into the stable,
versioned handoff contract consumed by the image-generation team.

The builder does not create model-specific prompts and does not call
an image-generation model or an LLM.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.creative_context.country_registry import (
    CountryCreativeRegistry,
    load_default_country_registry,
)
from app.creative_context.moment_resolver import (
    MarketMomentResolutionCollection,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    CreativeConstraints,
    CreativeDirection,
    CreativeThemeBrief,
    MomentResolutionRequest,
    ResolvedMarketMoment,
    ThemeFallback,
    ThemeResolutionResult,
)
from app.creative_context.theme_selector import (
    ThemeSelectionDecision,
)


# ============================================================
# Constants
# ============================================================
_DEFAULT_AVOID_ELEMENTS = (
    "competitor branding",
    "unsupported product claims",
)


# ============================================================
# List Helpers
# ============================================================
def _unique_strings(
    values: list[str],
) -> list[str]:
    """Return clean unique strings while preserving order."""

    result: list[str] = []

    for value in values:
        cleaned = value.strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    return result


# ============================================================
# Creative Direction
# ============================================================
def _build_concept(
    *,
    moment: ResolvedMarketMoment,
    business: BusinessCreativeContext,
) -> str:
    """Build a model-independent creative concept."""

    business_label = (
        business.industry
        or business.business_type
    )

    return (
        f"{moment.display_name} creative "
        f"direction for {business_label}"
    )


def _build_creative_direction(
    *,
    moment: ResolvedMarketMoment,
    business: BusinessCreativeContext,
) -> CreativeDirection:
    """Build the visual direction from the selected moment."""

    visual_tokens = _unique_strings(
        list(
            moment.visual_tokens
        )
    )

    return CreativeDirection(
        concept=_build_concept(
            moment=moment,
            business=business,
        ),
        mood_keywords=visual_tokens,
        visual_tokens=visual_tokens,
        palette_hints=[],
        lighting_hint=None,
        composition_hint=None,
    )


# ============================================================
# Creative Constraints
# ============================================================
def _build_constraints(
    *,
    moment: ResolvedMarketMoment,
    business: BusinessCreativeContext,
    target_country_code: str,
) -> CreativeConstraints:
    """Build brand and market constraints for the image team."""

    brand_rules = _unique_strings(
        list(
            business.brand_rules
        )
    )

    market_rules = [
        (
            "Use styling appropriate for "
            f"the target country "
            f"{target_country_code}."
        ),
    ]

    avoid_elements = _unique_strings(
        [
            *moment.avoid_elements,
            *_DEFAULT_AVOID_ELEMENTS,
        ]
    )

    return CreativeConstraints(
        brand_rules=brand_rules,
        market_rules=market_rules,
        avoid_elements=avoid_elements,
    )


# ============================================================
# One Brief
# ============================================================
def build_creative_theme_brief(
    *,
    moment: ResolvedMarketMoment,
    request: MomentResolutionRequest,
    business: BusinessCreativeContext,
    country_registry: (
        CountryCreativeRegistry | None
    ) = None,
) -> CreativeThemeBrief:
    """Build one image-team brief from one selected moment."""

    used_country_registry = (
        country_registry
        or load_default_country_registry()
    )

    country = used_country_registry.get(
        request.target_country_code
    )

    return CreativeThemeBrief(
        theme_key=moment.key,
        display_name=(
            moment.display_name
        ),
        source_moment=moment.key,
        moment_type=(
            moment.moment_type
        ),
        status=moment.status,
        target_country_code=(
            country.country_code
        ),
        market_groups=list(
            country.market_groups
        ),
        campaign_date=(
            request.campaign_date
        ),
        platform=request.platform,
        content_format=(
            request.content_format
        ),
        objective=request.objective,
        business_fit=(
            moment.business_fit
        ),
        confidence=(
            moment.selection_score
        ),
        valid_from=(
            moment.active_from
        ),
        valid_until=(
            moment.active_until
        ),
        creative_direction=(
            _build_creative_direction(
                moment=moment,
                business=business,
            )
        ),
        constraints=_build_constraints(
            moment=moment,
            business=business,
            target_country_code=(
                country.country_code
            ),
        ),
        reasons=list(
            moment.reasons
        ),
        evidence_references=list(
            moment.evidence_references
        ),
    )


# ============================================================
# Fallback
# ============================================================
def _build_fallback(
    *,
    decision: ThemeSelectionDecision,
) -> ThemeFallback:
    """Build the brand-only fallback contract."""

    reason = (
        decision.fallback_reason
        or (
            "Brand-only styling remains "
            "available as a safe fallback."
        )
    )

    return ThemeFallback(
        allowed=True,
        theme_key="brand_only",
        reason=reason,
    )


# ============================================================
# Final Handoff Result
# ============================================================
def build_theme_resolution_result(
    *,
    request: MomentResolutionRequest,
    business: BusinessCreativeContext,
    collection: (
        MarketMomentResolutionCollection
    ),
    decision: ThemeSelectionDecision,
    registry_version: str,
    country_registry: (
        CountryCreativeRegistry | None
    ) = None,
    resolution_id: UUID | None = None,
    generated_at: datetime | None = None,
) -> ThemeResolutionResult:
    """
    Build the final versioned handoff result.

    Optional resolution_id and generated_at values support stable
    contract tests and reproducible fixtures.
    """

    used_country_registry = (
        country_registry
        or load_default_country_registry()
    )

    primary_theme = None

    if decision.primary_moment is not None:
        primary_theme = (
            build_creative_theme_brief(
                moment=(
                    decision.primary_moment
                ),
                request=request,
                business=business,
                country_registry=(
                    used_country_registry
                ),
            )
        )

    secondary_accents = [
        build_creative_theme_brief(
            moment=moment,
            request=request,
            business=business,
            country_registry=(
                used_country_registry
            ),
        )
        for moment in (
            decision.secondary_moments
        )
    ]

    used_generated_at = (
        generated_at
        or datetime.now(
            UTC,
        )
    )

    if (
        used_generated_at.tzinfo
        is None
    ):
        used_generated_at = (
            used_generated_at.replace(
                tzinfo=UTC,
            )
        )

    warnings = _unique_strings(
        list(
            collection.warnings
        )
    )

    return ThemeResolutionResult(
        registry_version=(
            registry_version
        ),
        resolution_id=(
            resolution_id
            or uuid4()
        ),
        generated_at=(
            used_generated_at
        ),
        business_id=(
            business.business_id
        ),
        request=request,
        primary_theme=primary_theme,
        secondary_accents=(
            secondary_accents
        ),
        resolved_moments=list(
            collection.resolved_moments
        ),
        rejected_moments=list(
            decision.rejected_moments
        ),
        fallback=_build_fallback(
            decision=decision,
        ),
        warnings=warnings,
    )