"""
Market Moment Resolver

Combines country configuration, market-moment definitions, calendar
resolution, and business eligibility into deterministic resolved
moment candidates.

This module does not select a final theme and does not generate an
image prompt. Theme selection is handled by the next layer.
"""

from dataclasses import dataclass

from app.creative_context.country_registry import (
    CountryCreativeRegistry,
    load_default_country_registry,
)
from app.creative_context.date_resolvers import (
    MomentDateOverrideRegistry,
    load_default_moment_overrides,
    resolve_moment_window,
)
from app.creative_context.eligibility import (
    evaluate_moment_eligibility,
)
from app.creative_context.exceptions import (
    MomentDateResolutionError,
)
from app.creative_context.moment_registry import (
    MarketMomentRegistry,
    load_default_moment_registry,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    BusinessFitLevel,
    MarketMomentDefinition,
    MomentResolutionRequest,
    RejectedMarketMoment,
    ResolvedMarketMoment,
    ResolvedMomentWindow,
)


# ============================================================
# Resolver Result
# ============================================================
@dataclass(frozen=True, slots=True)
class MarketMomentResolutionCollection:
    """Resolved and rejected market moments for one request."""

    resolved_moments: tuple[
        ResolvedMarketMoment,
        ...,
    ]

    rejected_moments: tuple[
        RejectedMarketMoment,
        ...,
    ]

    warnings: tuple[str, ...]


# ============================================================
# Scoring
# ============================================================
_STATUS_SCORES = {
    "active": 0.45,
    "upcoming": 0.30,
    "cooldown": 0.10,
    "inactive": 0.00,
}


_FIT_SCORES = {
    "high": 0.30,
    "medium": 0.20,
    "low": 0.05,
    "not_applicable": 0.00,
}


def calculate_selection_score(
    *,
    status: str,
    business_fit: BusinessFitLevel,
    objective_supported: bool,
    priority: int,
) -> float:
    """
    Calculate a deterministic score in the range 0..1.

    Weight allocation:

    - Moment status: 45%.
    - Business fit: 30%.
    - Objective support: 10%.
    - Registry priority: 15%.

    Inactive moments always receive zero because they should not
    compete with active or upcoming moments.
    """

    if status == "inactive":
        return 0.0

    status_score = _STATUS_SCORES.get(
        status,
        0.0,
    )

    fit_score = _FIT_SCORES.get(
        business_fit,
        0.0,
    )

    objective_score = (
        0.10
        if objective_supported
        else 0.0
    )

    normalized_priority = (
        max(
            0,
            min(
                priority,
                100,
            ),
        )
        / 100
    )

    priority_score = (
        normalized_priority
        * 0.15
    )

    return round(
        min(
            1.0,
            status_score
            + fit_score
            + objective_score
            + priority_score,
        ),
        4,
    )


# ============================================================
# Explanation Helpers
# ============================================================
def _status_reason(
    window: ResolvedMomentWindow,
) -> str:
    """Build a clear explanation for the resolved date status."""

    if window.status == "active":
        return (
            "The campaign date is inside "
            "the active moment window."
        )

    if window.status == "upcoming":
        return (
            "The campaign date is inside "
            "the configured lead window."
        )

    if window.status == "cooldown":
        return (
            "The campaign date is inside "
            "the configured cooldown window."
        )

    return (
        "The campaign date is outside "
        "the lead, active, and cooldown "
        "windows."
    )


def _rejection_reason(
    *,
    status: str,
    country_applicable: bool,
    objective_supported: bool,
    business_fit: BusinessFitLevel,
) -> str:
    """Return the primary reason a moment is not eligible."""

    if not country_applicable:
        return (
            "The target country is outside "
            "the configured moment scope."
        )

    if status not in {
        "active",
        "upcoming",
    }:
        return (
            "The moment is not active or "
            "upcoming for the campaign date."
        )

    if business_fit == "not_applicable":
        return (
            "The moment is not applicable "
            "to the business type."
        )

    if business_fit == "low":
        return (
            "The moment has low business fit "
            "and is not selected automatically."
        )

    if not objective_supported:
        return (
            "The campaign objective is not "
            "supported by the moment."
        )

    return (
        "The moment did not satisfy automatic "
        "eligibility requirements."
    )


# ============================================================
# One-Moment Resolution
# ============================================================
def resolve_market_moment(
    *,
    moment: MarketMomentDefinition,
    request: MomentResolutionRequest,
    business: BusinessCreativeContext,
    country_registry: CountryCreativeRegistry,
    overrides: MomentDateOverrideRegistry,
) -> tuple[
    ResolvedMarketMoment | None,
    RejectedMarketMoment | None,
    str | None,
]:
    """
    Resolve one market moment.

    Returns:

    - A resolved moment when its date can be calculated.
    - A rejected moment when it cannot compete automatically.
    - An optional warning for missing country/year configuration.
    """

    country = country_registry.get(
        request.target_country_code
    )

    eligibility = (
        evaluate_moment_eligibility(
            moment=moment,
            country=country,
            business_type=(
                business.business_type
            ),
            objective=request.objective,
        )
    )

    if not eligibility.country_applicable:
        rejected = RejectedMarketMoment(
            key=moment.key,
            display_name=(
                moment.display_name
            ),
            status="inactive",
            business_fit=(
                eligibility.business_fit
            ),
            reason=(
                "The target country is outside "
                "the configured moment scope."
            ),
        )

        return (
            None,
            rejected,
            None,
        )

    try:
        window = resolve_moment_window(
            moment=moment,
            country=country,
            campaign_date=(
                request.campaign_date
            ),
            overrides=overrides,
        )
    except MomentDateResolutionError as error:
        warning = (
            f"{moment.key}: {error}"
        )

        rejected = RejectedMarketMoment(
            key=moment.key,
            display_name=(
                moment.display_name
            ),
            status="inactive",
            business_fit=(
                eligibility.business_fit
            ),
            reason=str(error),
        )

        return (
            None,
            rejected,
            warning,
        )

    automatically_eligible = (
        eligibility.automatically_eligible
        and window.status
        in {
            "active",
            "upcoming",
        }
    )

    selection_score = (
        calculate_selection_score(
            status=window.status,
            business_fit=(
                eligibility.business_fit
            ),
            objective_supported=(
                eligibility
                .objective_supported
            ),
            priority=moment.priority,
        )
    )

    reasons = [
        _status_reason(
            window
        ),
        *eligibility.reasons,
    ]

    evidence_references = [
        window.evidence_reference,
        (
            f"moment-definition:"
            f"{moment.key}:"
            f"{moment.version}"
        ),
        (
            f"country-profile:"
            f"{country.country_code}:"
            f"{country.version}"
        ),
        (
            "business-context:"
            f"{business.business_id}"
        ),
    ]

    resolved = ResolvedMarketMoment(
        key=moment.key,
        display_name=(
            moment.display_name
        ),
        moment_type=(
            moment.moment_type
        ),
        campaign_date=(
            request.campaign_date
        ),
        active_from=(
            window.active_from
        ),
        active_until=(
            window.active_until
        ),
        status=window.status,
        business_fit=(
            eligibility.business_fit
        ),
        eligible=(
            automatically_eligible
        ),
        priority=moment.priority,
        selection_score=(
            selection_score
        ),
        visual_tokens=list(
            moment.visual_tokens
        ),
        avoid_elements=list(
            moment.default_avoid_elements
        ),
        reasons=reasons,
        evidence_references=(
            evidence_references
        ),
    )

    rejected = None

    if not automatically_eligible:
        rejected = RejectedMarketMoment(
            key=moment.key,
            display_name=(
                moment.display_name
            ),
            status=window.status,
            business_fit=(
                eligibility.business_fit
            ),
            reason=_rejection_reason(
                status=window.status,
                country_applicable=(
                    eligibility
                    .country_applicable
                ),
                objective_supported=(
                    eligibility
                    .objective_supported
                ),
                business_fit=(
                    eligibility.business_fit
                ),
            ),
        )

    return (
        resolved,
        rejected,
        None,
    )


# ============================================================
# Full Registry Resolution
# ============================================================
def resolve_market_moments(
    *,
    request: MomentResolutionRequest,
    business: BusinessCreativeContext,
    country_registry: (
        CountryCreativeRegistry | None
    ) = None,
    moment_registry: (
        MarketMomentRegistry | None
    ) = None,
    overrides: (
        MomentDateOverrideRegistry | None
    ) = None,
) -> MarketMomentResolutionCollection:
    """
    Resolve every enabled market moment for one business request.

    The target country is taken from the request because a campaign
    may target a market different from the business home country.
    """

    used_country_registry = (
        country_registry
        or load_default_country_registry()
    )

    used_moment_registry = (
        moment_registry
        or load_default_moment_registry()
    )

    used_overrides = (
        overrides
        or load_default_moment_overrides()
    )

    used_country_registry.get(
        request.target_country_code
    )

    resolved_moments: list[
        ResolvedMarketMoment
    ] = []

    rejected_moments: list[
        RejectedMarketMoment
    ] = []

    warnings: list[str] = []

    for moment in (
        used_moment_registry.list_enabled()
    ):
        (
            resolved,
            rejected,
            warning,
        ) = resolve_market_moment(
            moment=moment,
            request=request,
            business=business,
            country_registry=(
                used_country_registry
            ),
            overrides=used_overrides,
        )

        if resolved is not None:
            resolved_moments.append(
                resolved
            )

        if rejected is not None:
            rejected_moments.append(
                rejected
            )

        if warning is not None:
            warnings.append(
                warning
            )

    resolved_moments.sort(
        key=lambda item: (
            -item.selection_score,
            -item.priority,
            item.key,
        )
    )

    rejected_moments.sort(
        key=lambda item: (
            item.key
        )
    )

    warnings.sort()

    return MarketMomentResolutionCollection(
        resolved_moments=tuple(
            resolved_moments
        ),
        rejected_moments=tuple(
            rejected_moments
        ),
        warnings=tuple(
            warnings
        ),
    )