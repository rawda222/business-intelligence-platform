"""
Creative Theme Selector

Selects one primary market moment and optional secondary moments
from a resolved market-moment collection.

Selection is deterministic and contains no LLM or image-generation
logic.
"""

from dataclasses import dataclass

from app.creative_context.exceptions import (
    ThemeSelectionError,
)
from app.creative_context.moment_resolver import (
    MarketMomentResolutionCollection,
)
from app.creative_context.schemas import (
    MomentResolutionRequest,
    RejectedMarketMoment,
    ResolvedMarketMoment,
    SelectionMode,
)


# ============================================================
# Selection Result
# ============================================================
@dataclass(frozen=True, slots=True)
class ThemeSelectionDecision:
    """Internal deterministic theme-selection result."""

    selection_mode: SelectionMode

    primary_moment: (
        ResolvedMarketMoment | None
    )

    secondary_moments: tuple[
        ResolvedMarketMoment,
        ...,
    ]

    rejected_moments: tuple[
        RejectedMarketMoment,
        ...,
    ]

    fallback_reason: str | None


# ============================================================
# Sorting
# ============================================================
_STATUS_ORDER = {
    "active": 0,
    "upcoming": 1,
    "cooldown": 2,
    "inactive": 3,
}


def _candidate_sort_key(
    moment: ResolvedMarketMoment,
) -> tuple[
    int,
    float,
    int,
    str,
]:
    """Return the deterministic selection order."""

    return (
        _STATUS_ORDER.get(
            moment.status,
            99,
        ),
        -moment.selection_score,
        -moment.priority,
        moment.key,
    )


def _sorted_automatic_candidates(
    moments: tuple[
        ResolvedMarketMoment,
        ...,
    ],
) -> list[
    ResolvedMarketMoment
]:
    """Return moments eligible for automatic selection."""

    candidates = [
        moment
        for moment in moments
        if (
            moment.eligible
            and moment.status
            in {
                "active",
                "upcoming",
            }
        )
    ]

    candidates.sort(
        key=_candidate_sort_key,
    )

    return candidates


# ============================================================
# Rejection Helpers
# ============================================================
def _rejected_from_resolved(
    moment: ResolvedMarketMoment,
    *,
    reason: str,
) -> RejectedMarketMoment:
    """Convert an unselected resolved moment into a rejection."""

    return RejectedMarketMoment(
        key=moment.key,
        display_name=(
            moment.display_name
        ),
        status=moment.status,
        business_fit=(
            moment.business_fit
        ),
        reason=reason,
    )


def _merge_rejections(
    *,
    existing: tuple[
        RejectedMarketMoment,
        ...,
    ],
    additional: list[
        RejectedMarketMoment
    ],
) -> tuple[
    RejectedMarketMoment,
    ...,
]:
    """
    Merge rejection entries using one deterministic entry per key.

    Existing resolver rejections take precedence.
    """

    merged: dict[
        str,
        RejectedMarketMoment,
    ] = {
        item.key: item
        for item in existing
    }

    for item in additional:
        if item.key not in merged:
            merged[item.key] = item

    return tuple(
        merged[key]
        for key in sorted(
            merged
        )
    )


# ============================================================
# Brand-Only Selection
# ============================================================
def _select_brand_only(
    *,
    request: MomentResolutionRequest,
    collection: (
        MarketMomentResolutionCollection
    ),
) -> ThemeSelectionDecision:
    """Return an explicit brand-only decision."""

    additional_rejections = [
        _rejected_from_resolved(
            moment,
            reason=(
                "Brand-only selection mode "
                "was requested."
            ),
        )
        for moment in (
            collection.resolved_moments
        )
    ]

    return ThemeSelectionDecision(
        selection_mode=(
            request.selection_mode
        ),
        primary_moment=None,
        secondary_moments=(),
        rejected_moments=(
            _merge_rejections(
                existing=(
                    collection.rejected_moments
                ),
                additional=(
                    additional_rejections
                ),
            )
        ),
        fallback_reason=(
            "Brand-only selection mode "
            "was requested."
        ),
    )


# ============================================================
# Automatic Selection
# ============================================================
def _select_automatic(
    *,
    request: MomentResolutionRequest,
    collection: (
        MarketMomentResolutionCollection
    ),
    max_secondary_moments: int,
) -> ThemeSelectionDecision:
    """Select the highest-ranked automatically eligible moment."""

    candidates = (
        _sorted_automatic_candidates(
            collection.resolved_moments
        )
    )

    if not candidates:
        return ThemeSelectionDecision(
            selection_mode=(
                request.selection_mode
            ),
            primary_moment=None,
            secondary_moments=(),
            rejected_moments=(
                collection.rejected_moments
            ),
            fallback_reason=(
                "No eligible active or "
                "upcoming market moment "
                "was available."
            ),
        )

    primary = candidates[0]

    secondary = tuple(
        candidates[
            1:
            1 + max_secondary_moments
        ]
    )

    selected_keys = {
        primary.key,
        *(
            moment.key
            for moment in secondary
        ),
    }

    unselected = [
        _rejected_from_resolved(
            moment,
            reason=(
                "A higher-ranked eligible "
                "moment was selected."
            ),
        )
        for moment in candidates
        if moment.key not in selected_keys
    ]

    return ThemeSelectionDecision(
        selection_mode=(
            request.selection_mode
        ),
        primary_moment=primary,
        secondary_moments=secondary,
        rejected_moments=(
            _merge_rejections(
                existing=(
                    collection.rejected_moments
                ),
                additional=unselected,
            )
        ),
        fallback_reason=None,
    )


# ============================================================
# User Override Selection
# ============================================================
def _select_user_override(
    *,
    request: MomentResolutionRequest,
    collection: (
        MarketMomentResolutionCollection
    ),
    max_secondary_moments: int,
) -> ThemeSelectionDecision:
    """Select an explicitly requested moment when safely usable."""

    override_key = (
        request.moment_override
    )

    if override_key is None:
        raise ThemeSelectionError(
            "User override mode requires "
            "moment_override."
        )

    override = next(
        (
            moment
            for moment in (
                collection.resolved_moments
            )
            if moment.key == override_key
        ),
        None,
    )

    if override is None:
        raise ThemeSelectionError(
            "The requested moment could "
            "not be resolved for the "
            "target country."
        )

    if override.status not in {
        "active",
        "upcoming",
    }:
        raise ThemeSelectionError(
            "The requested moment is not "
            "active or upcoming."
        )

    if (
        override.business_fit
        == "not_applicable"
    ):
        raise ThemeSelectionError(
            "The requested moment is not "
            "applicable to the business "
            "type."
        )

    if (
        not override.eligible
        and override.business_fit
        != "low"
    ):
        raise ThemeSelectionError(
            "The requested moment does not "
            "satisfy campaign eligibility "
            "requirements."
        )

    automatic_candidates = (
        _sorted_automatic_candidates(
            collection.resolved_moments
        )
    )

    secondary = tuple(
        moment
        for moment in (
            automatic_candidates
        )
        if moment.key != override.key
    )[:max_secondary_moments]

    selected_keys = {
        override.key,
        *(
            moment.key
            for moment in secondary
        ),
    }

    additional_rejections = [
        _rejected_from_resolved(
            moment,
            reason=(
                "Another moment was selected "
                "through user override."
            ),
        )
        for moment in (
            collection.resolved_moments
        )
        if moment.key not in selected_keys
    ]

    return ThemeSelectionDecision(
        selection_mode=(
            request.selection_mode
        ),
        primary_moment=override,
        secondary_moments=secondary,
        rejected_moments=(
            _merge_rejections(
                existing=(
                    collection.rejected_moments
                ),
                additional=(
                    additional_rejections
                ),
            )
        ),
        fallback_reason=None,
    )


# ============================================================
# Public Entry Point
# ============================================================
def select_theme_moments(
    *,
    request: MomentResolutionRequest,
    collection: (
        MarketMomentResolutionCollection
    ),
    max_secondary_moments: int = 1,
) -> ThemeSelectionDecision:
    """
    Select the primary and secondary market moments.

    The same request and collection always produce the same result.
    """

    if (
        max_secondary_moments < 0
        or max_secondary_moments > 3
    ):
        raise ThemeSelectionError(
            "max_secondary_moments must "
            "be between 0 and 3."
        )

    if request.selection_mode == "brand_only":
        return _select_brand_only(
            request=request,
            collection=collection,
        )

    if (
        request.selection_mode
        == "user_override"
    ):
        return _select_user_override(
            request=request,
            collection=collection,
            max_secondary_moments=(
                max_secondary_moments
            ),
        )

    return _select_automatic(
        request=request,
        collection=collection,
        max_secondary_moments=(
            max_secondary_moments
        ),
    )