
"""
Market Moment Business Eligibility

Evaluates whether a configured market moment is suitable for a
business, target country, and campaign objective.

The module does not resolve dates and does not select a final theme.
It only produces deterministic eligibility and business-fit signals.
"""

from dataclasses import dataclass

from app.creative_context.schemas import (
    BusinessFitLevel,
    CountryCreativeProfile,
    MarketMomentDefinition,
)


# ============================================================
# Eligibility Result
# ============================================================
@dataclass(frozen=True, slots=True)
class MomentEligibilityResult:
    """Deterministic eligibility result for one market moment."""

    country_applicable: bool

    objective_supported: bool

    business_fit: BusinessFitLevel

    automatically_eligible: bool

    reasons: tuple[str, ...]


# ============================================================
# Country Scope
# ============================================================
def is_country_applicable(
    *,
    moment: MarketMomentDefinition,
    country: CountryCreativeProfile,
) -> bool:
    """
    Return whether the moment applies to the target country.

    Scope precedence:

    1. Explicit country list.
    2. Market-group intersection.
    3. Global when neither scope is configured.
    """

    explicit_countries = set(
        moment.applicable_countries
    )

    applicable_groups = set(
        moment.applicable_market_groups
    )

    country_groups = set(
        country.market_groups
    )

    if explicit_countries:
        return (
            country.country_code
            in explicit_countries
        )

    if applicable_groups:
        return bool(
            applicable_groups
            & country_groups
        )

    return True


# ============================================================
# Business Fit
# ============================================================
def resolve_business_fit(
    *,
    moment: MarketMomentDefinition,
    business_type: str,
) -> BusinessFitLevel:
    """Resolve configured business fit for one moment."""

    normalized_type = (
        business_type.strip().lower()
    )

    if (
        normalized_type
        in moment.excluded_business_types
    ):
        return "not_applicable"

    if (
        normalized_type
        in moment.high_fit_business_types
    ):
        return "high"

    if (
        normalized_type
        in moment.medium_fit_business_types
    ):
        return "medium"

    if (
        normalized_type
        in moment.low_fit_business_types
    ):
        return "low"

    return "not_applicable"


# ============================================================
# Objective Support
# ============================================================
def is_objective_supported(
    *,
    moment: MarketMomentDefinition,
    objective: str,
) -> bool:
    """
    Return whether the campaign objective is supported.

    An empty objective list means that the moment does not restrict
    campaign objectives.
    """

    configured_objectives = {
        value.strip().lower()
        for value in (
            moment.applicable_objectives
        )
        if value.strip()
    }

    if not configured_objectives:
        return True

    normalized_objective = (
        objective.strip().lower()
    )

    return (
        normalized_objective
        in configured_objectives
    )


# ============================================================
# Public Evaluation
# ============================================================
def evaluate_moment_eligibility(
    *,
    moment: MarketMomentDefinition,
    country: CountryCreativeProfile,
    business_type: str,
    objective: str,
) -> MomentEligibilityResult:
    """
    Evaluate country, business, and objective eligibility.

    Automatic selection accepts only high and medium business fit.
    Low fit remains available for a future explicit user override.
    """

    country_applicable = (
        is_country_applicable(
            moment=moment,
            country=country,
        )
    )

    business_fit = (
        resolve_business_fit(
            moment=moment,
            business_type=business_type,
        )
    )

    objective_supported = (
        is_objective_supported(
            moment=moment,
            objective=objective,
        )
    )

    automatically_eligible = (
        country_applicable
        and objective_supported
        and business_fit
        in {
            "high",
            "medium",
        }
    )

    reasons: list[str] = []

    if country_applicable:
        reasons.append(
            "The target country is inside "
            "the configured moment scope."
        )
    else:
        reasons.append(
            "The target country is outside "
            "the configured moment scope."
        )

    if business_fit == "high":
        reasons.append(
            "The moment has high fit for "
            "the business type."
        )
    elif business_fit == "medium":
        reasons.append(
            "The moment has medium fit for "
            "the business type."
        )
    elif business_fit == "low":
        reasons.append(
            "The moment has low fit for "
            "the business type and is not "
            "selected automatically."
        )
    else:
        reasons.append(
            "The moment is not applicable "
            "to the business type."
        )

    if objective_supported:
        reasons.append(
            "The campaign objective is "
            "supported by the moment."
        )
    else:
        reasons.append(
            "The campaign objective is not "
            "supported by the moment."
        )

    return MomentEligibilityResult(
        country_applicable=(
            country_applicable
        ),
        objective_supported=(
            objective_supported
        ),
        business_fit=business_fit,
        automatically_eligible=(
            automatically_eligible
        ),
        reasons=tuple(
            reasons
        ),
    )