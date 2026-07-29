"""
Unified SWOT Workflow Service

One entry point that runs the complete grounded SWOT workflow and
automatically selects the correct mode:

- initial: no approved SWOT baseline exists yet.
- update: an approved, Strategy-ready SWOT baseline already exists.

The workflow never approves a proposal and never runs Strategy.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.services.business_trend_intelligence_service import (
    build_business_trend_intelligence,
)
from app.services.business_trend_report_service import (
    build_business_trend_report,
)
from app.services.cross_source_customer_voice_loader import (
    load_cross_source_customer_voice,
)
from app.services.grounded_swot_generation_service import (
    generate_grounded_swot,
)
from app.services.grounded_swot_proposal_service import (
    build_grounded_swot_initial_proposal,
    build_grounded_swot_update_proposal,
)
from app.services.legacy_swot_adapter import (
    normalize_legacy_swot,
)
from app.services.raw_customer_voice_adapter import (
    build_customer_voice_from_raw_data,
)
from app.services.strong_swot_input_service import (
    build_strong_swot_input,
)
from app.services.swot_strategy_persistence_service import (
    get_latest_approved_swot_report,
    save_swot_update_proposal,
)


_DEFAULT_BASELINE_SOURCES = (
    "business_profile",
    "google_maps_reviews",
)


@dataclass(frozen=True, slots=True)
class UnifiedSwotWorkflowResult:
    """Complete result of one unified SWOT workflow run."""

    business_id: UUID

    mode: str

    baseline_report_id: UUID | None

    customer_voice: Any

    trend_report: Any

    trend_intelligence: Any

    strong_swot_bundle: Any

    generation: Any

    grounded_proposal: Any | None

    persisted_proposal: Any | None

    proposal_id: UUID | None

    source_coverage: tuple[str, ...]

    warnings: tuple[str, ...]

    coverage_level: str = "grounded_full"


def _ensure_utc(
    value: datetime,
) -> datetime:
    """Return one timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )


def _validate_range(
    *,
    range_start: datetime,
    range_end: datetime,
) -> tuple[
    datetime,
    datetime,
]:
    """Normalize and validate one half-open workflow range."""

    normalized_start = _ensure_utc(
        range_start
    )

    normalized_end = _ensure_utc(
        range_end
    )

    if normalized_start >= normalized_end:
        raise ValueError(
            "range_start must be earlier than range_end."
        )

    return (
        normalized_start,
        normalized_end,
    )


def _uuid_value(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    """Normalize one UUID value or fail closed."""

    if isinstance(
        value,
        UUID,
    ):
        return value

    try:
        return UUID(
            str(
                value
            )
        )
    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as error:
        raise ValueError(
            f"{field_name} must be a valid UUID."
        ) from error


def _baseline_source_coverage(
    approved_swot: Any,
) -> tuple[str, ...]:
    """Read approved SWOT source coverage with a fallback."""

    raw_sources = getattr(
        approved_swot,
        "source_coverage",
        (),
    )

    if not isinstance(
        raw_sources,
        (
            list,
            tuple,
        ),
    ):
        raw_sources = ()

    result: list[str] = []

    for source in raw_sources:
        if not isinstance(
            source,
            str,
        ):
            continue

        cleaned = source.strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    if result:
        return tuple(
            result
        )

    return _DEFAULT_BASELINE_SOURCES


async def run_unified_swot_workflow(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    range_start: datetime,
    range_end: datetime,
    review_source: str = "google_maps",
    max_engagement_curves: int = 5,
    load_approved_swot_fn: Any = (
        get_latest_approved_swot_report
    ),
    load_customer_voice_fn: Any = (
        load_cross_source_customer_voice
    ),
    build_trend_report_fn: Any = (
        build_business_trend_report
    ),
    build_trend_intelligence_fn: Any = (
        build_business_trend_intelligence
    ),
    build_bundle_fn: Any = (
        build_strong_swot_input
    ),
    generate_fn: Any = (
        generate_grounded_swot
    ),
    build_initial_proposal_fn: Any = (
        build_grounded_swot_initial_proposal
    ),
    build_update_proposal_fn: Any = (
        build_grounded_swot_update_proposal
    ),
    normalize_baseline_fn: Any = (
        normalize_legacy_swot
    ),
    save_proposal_fn: Any = (
        save_swot_update_proposal
    ),
) -> UnifiedSwotWorkflowResult:
    """
    Run the unified grounded SWOT workflow.

    The workflow builds customer voice, trend intelligence, a Strong
    SWOT input bundle, and a grounded SWOT generation. It then builds
    an initial or update proposal automatically and persists it.
    """

    (
        normalized_start,
        normalized_end,
    ) = _validate_range(
        range_start=range_start,
        range_end=range_end,
    )

    if max_engagement_curves < 0:
        raise ValueError(
            "max_engagement_curves must be non-negative."
        )

    approved_swot = await load_approved_swot_fn(
        business_id=business_id,
    )

    mode = (
        "initial"
        if approved_swot is None
        else "update"
    )

    customer_voice = (
        await load_customer_voice_fn(
            business_id=business_id,
            business_name=business_name,
            business_type=business_type,
            range_start=normalized_start,
            range_end=normalized_end,
        )
    )

    trend_report = (
        await build_trend_report_fn(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
            review_source=review_source,
            max_engagement_curves=(
                max_engagement_curves
            ),
        )
    )

    trend_intelligence = (
        build_trend_intelligence_fn(
            trend_report
        )
    )

    strong_swot_bundle = build_bundle_fn(
        customer_voice=customer_voice,
        trend_intelligence=(
            trend_intelligence
        ),
    )

    if (
        strong_swot_bundle.business_id
        != business_id
    ):
        raise ValueError(
            "Strong SWOT bundle business_id does not "
            "match the requested business_id."
        )

    generation = generate_fn(
        bundle=strong_swot_bundle,
    )

    baseline = None

    baseline_report_id = None

    if mode == "initial":
        grounded_proposal = (
            build_initial_proposal_fn(
                bundle=strong_swot_bundle,
                generation=generation,
            )
        )
    else:
        baseline_report_id = _uuid_value(
            getattr(
                approved_swot,
                "report_id",
                None,
            ),
            field_name=(
                "approved SWOT report_id"
            ),
        )

        baseline = normalize_baseline_fn(
            business_id=business_id,
            report_id=baseline_report_id,
            engine_version=str(
                getattr(
                    approved_swot,
                    "engine_version",
                    "unknown",
                )
                or "unknown"
            ),
            swot_report=getattr(
                approved_swot,
                "swot_report",
                {},
            ),
            source_coverage=(
                _baseline_source_coverage(
                    approved_swot
                )
            ),
        )

        grounded_proposal = (
            build_update_proposal_fn(
                baseline=baseline,
                bundle=strong_swot_bundle,
                generation=generation,
            )
        )

    if (
        grounded_proposal.business_id
        != business_id
    ):
        raise ValueError(
            "Grounded proposal business_id does not "
            "match the requested business_id."
        )

    customer_evidence_count = len(
        getattr(
            customer_voice,
            "business_reviews",
            (),
        )
    )

    if grounded_proposal.safe_for_approval_workflow:
        coverage_level = "grounded_full"
    elif customer_evidence_count > 0:
        coverage_level = "provisional"
    else:
        coverage_level = "insufficient"

    if coverage_level == "insufficient":
        return UnifiedSwotWorkflowResult(
            business_id=business_id,
            mode=mode,
            baseline_report_id=(
                baseline_report_id
            ),
            customer_voice=customer_voice,
            trend_report=trend_report,
            trend_intelligence=(
                trend_intelligence
            ),
            strong_swot_bundle=(
                strong_swot_bundle
            ),
            generation=generation,
            grounded_proposal=(
                grounded_proposal
            ),
            persisted_proposal=None,
            proposal_id=None,
            source_coverage=(),
            warnings=(
                "insufficient_customer_evidence",
                "external_analysis_unavailable",
                "connect_more_sources_or_add_reviews",
            ),
            coverage_level=coverage_level,
        )

    if not grounded_proposal.safe_for_approval_workflow:
        return UnifiedSwotWorkflowResult(
            business_id=business_id,
            mode=mode,
            baseline_report_id=(
                baseline_report_id
            ),
            customer_voice=customer_voice,
            trend_report=trend_report,
            trend_intelligence=(
                trend_intelligence
            ),
            strong_swot_bundle=(
                strong_swot_bundle
            ),
            generation=generation,
            grounded_proposal=(
                grounded_proposal
            ),
            persisted_proposal=None,
            proposal_id=None,
            source_coverage=(),
            warnings=(
                "limited_customer_evidence",
                "provisional_swot_pending_more_data",
            ),
            coverage_level=coverage_level,
        )

    persisted_proposal = (
        await save_proposal_fn(
            baseline=baseline,
            generation=generation,
            grounded_result=(
                grounded_proposal
            ),
        )
    )

    persisted_business_id = _uuid_value(
        getattr(
            persisted_proposal,
            "business_id",
            None,
        ),
        field_name=(
            "persisted proposal business_id"
        ),
    )

    if persisted_business_id != business_id:
        raise ValueError(
            "Persisted proposal business_id does not "
            "match the requested business_id."
        )

    proposal_id = _uuid_value(
        getattr(
            persisted_proposal,
            "proposal_id",
            None,
        ),
        field_name=(
            "persisted proposal_id"
        ),
    )

    source_coverage = tuple(
        grounded_proposal
        .proposal
        .current_sources
    )

    warnings = tuple(
        grounded_proposal.warnings
    )

    return UnifiedSwotWorkflowResult(
        business_id=business_id,
        mode=mode,
        baseline_report_id=(
            baseline_report_id
        ),
        customer_voice=customer_voice,
        trend_report=trend_report,
        trend_intelligence=(
            trend_intelligence
        ),
        strong_swot_bundle=(
            strong_swot_bundle
        ),
        generation=generation,
        grounded_proposal=(
            grounded_proposal
        ),
        persisted_proposal=(
            persisted_proposal
        ),
        proposal_id=proposal_id,
        source_coverage=(
            source_coverage
        ),
        warnings=warnings,
    )

async def run_unified_swot_workflow_from_raw_data(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    raw_data: dict[str, Any],
    range_start: datetime,
    range_end: datetime,
    review_source: str = "google_maps",
    max_engagement_curves: int = 5,
    load_approved_swot_fn: Any = (
        get_latest_approved_swot_report
    ),
    build_trend_report_fn: Any = (
        build_business_trend_report
    ),
    build_trend_intelligence_fn: Any = (
        build_business_trend_intelligence
    ),
    build_bundle_fn: Any = (
        build_strong_swot_input
    ),
    generate_fn: Any = (
        generate_grounded_swot
    ),
    build_initial_proposal_fn: Any = (
        build_grounded_swot_initial_proposal
    ),
    build_update_proposal_fn: Any = (
        build_grounded_swot_update_proposal
    ),
    normalize_baseline_fn: Any = (
        normalize_legacy_swot
    ),
    save_proposal_fn: Any = (
        save_swot_update_proposal
    ),
) -> UnifiedSwotWorkflowResult:
    """
    Run the unified grounded SWOT workflow directly from raw data.

    When the grounded generation is fully safe, a grounded_full
    proposal is persisted. When it produced accepted items but was
    not fully safe (e.g. one blocked item), a PROVISIONAL proposal is
    still built from the accepted items and persisted, so the user
    can review, approve, and continue to Strategy with an explicit
    low-confidence warning. Only a generation with zero accepted
    items stops before persistence.
    """

    (
        normalized_start,
        normalized_end,
    ) = _validate_range(
        range_start=range_start,
        range_end=range_end,
    )

    if max_engagement_curves < 0:
        raise ValueError(
            "max_engagement_curves must be non-negative."
        )

    approved_swot = await load_approved_swot_fn(
        business_id=business_id,
    )

    mode = (
        "initial"
        if approved_swot is None
        else "update"
    )

    customer_voice = (
        build_customer_voice_from_raw_data(
            business_id=business_id,
            business_name=business_name,
            business_type=business_type,
            raw_data=raw_data,
        )
    )

    trend_report = (
        await build_trend_report_fn(
            business_id=business_id,
            range_start=normalized_start,
            range_end=normalized_end,
            review_source=review_source,
            max_engagement_curves=(
                max_engagement_curves
            ),
        )
    )

    trend_intelligence = (
        build_trend_intelligence_fn(
            trend_report
        )
    )

    strong_swot_bundle = build_bundle_fn(
        customer_voice=customer_voice,
        trend_intelligence=(
            trend_intelligence
        ),
    )

    if (
        strong_swot_bundle.business_id
        != business_id
    ):
        raise ValueError(
            "Strong SWOT bundle business_id does not "
            "match the requested business_id."
        )

    generation = generate_fn(
        bundle=strong_swot_bundle,
    )

    customer_evidence_count = len(
        getattr(
            customer_voice,
            "business_reviews",
            (),
        )
    )

    accepted_count = len(
        getattr(
            generation,
            "accepted_items",
            (),
        )
    )

    generation_is_safe = bool(
        getattr(
            generation,
            "safe_for_update_proposal",
            False,
        )
    )

    # مفيش أي عنصر مقبول → مش قادرين نبني SWOT إطلاقًا
    if accepted_count == 0:
        coverage_level = (
            "provisional"
            if customer_evidence_count > 0
            else "insufficient"
        )

        return UnifiedSwotWorkflowResult(
            business_id=business_id,
            mode=mode,
            baseline_report_id=None,
            customer_voice=customer_voice,
            trend_report=trend_report,
            trend_intelligence=(
                trend_intelligence
            ),
            strong_swot_bundle=(
                strong_swot_bundle
            ),
            generation=generation,
            grounded_proposal=None,
            persisted_proposal=None,
            proposal_id=None,
            source_coverage=(),
            warnings=(
                "provisional_swot_"
                "no_accepted_items",
                "provisional_swot_"
                "pending_more_data",
            ),
            coverage_level=coverage_level,
        )

    # فيه عناصر مقبولة لكن مش كلها نضيف → provisional قابل للحفظ والاعتماد
    is_provisional = not generation_is_safe

    baseline = None

    baseline_report_id = None

    if mode == "initial":
        grounded_proposal = (
            build_initial_proposal_fn(
                bundle=strong_swot_bundle,
                generation=generation,
                allow_provisional=is_provisional,
            )
        )
    else:
        baseline_report_id = _uuid_value(
            getattr(
                approved_swot,
                "report_id",
                None,
            ),
            field_name=(
                "approved SWOT report_id"
            ),
        )

        baseline = normalize_baseline_fn(
            business_id=business_id,
            report_id=baseline_report_id,
            engine_version=str(
                getattr(
                    approved_swot,
                    "engine_version",
                    "unknown",
                )
                or "unknown"
            ),
            swot_report=getattr(
                approved_swot,
                "swot_report",
                {},
            ),
            source_coverage=(
                _baseline_source_coverage(
                    approved_swot
                )
            ),
        )

        grounded_proposal = (
            build_update_proposal_fn(
                baseline=baseline,
                bundle=strong_swot_bundle,
                generation=generation,
            )
        )

    if (
        grounded_proposal.business_id
        != business_id
    ):
        raise ValueError(
            "Grounded proposal business_id does not "
            "match the requested business_id."
        )

    if not (
        grounded_proposal
        .safe_for_approval_workflow
    ):
        raise ValueError(
            "Grounded SWOT proposal could not be built "
            "for the approval workflow."
        )

    persisted_proposal = (
        await save_proposal_fn(
            baseline=baseline,
            generation=generation,
            grounded_result=(
                grounded_proposal
            ),
        )
    )

    proposal_id = _uuid_value(
        getattr(
            persisted_proposal,
            "proposal_id",
            None,
        ),
        field_name=(
            "persisted proposal_id"
        ),
    )

    source_coverage = tuple(
        grounded_proposal
        .proposal
        .current_sources
    )

    warnings = tuple(
        grounded_proposal.warnings
    )

    return UnifiedSwotWorkflowResult(
        business_id=business_id,
        mode=mode,
        baseline_report_id=(
            baseline_report_id
        ),
        customer_voice=customer_voice,
        trend_report=trend_report,
        trend_intelligence=(
            trend_intelligence
        ),
        strong_swot_bundle=(
            strong_swot_bundle
        ),
        generation=generation,
        grounded_proposal=(
            grounded_proposal
        ),
        persisted_proposal=(
            persisted_proposal
        ),
        proposal_id=proposal_id,
        source_coverage=(
            source_coverage
        ),
        coverage_level=(
            "provisional"
            if is_provisional
            else "grounded_full"
        ),
        warnings=warnings,
    )

def _build_provisional_swot_report(
    *,
    bundle: Any,
) -> dict[str, list[dict[str, Any]]]:
    """
    Build a provisional SWOT from grounded trend candidates
    when the LLM path yields no accepted items.
    Every item is low-confidence and flagged for human review.
    """

    report: dict[str, list[dict[str, Any]]] = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    }

    candidates = getattr(
        bundle,
        "trend_candidates",
        (),
    )

    quadrant_map = {
        "strengths": "strengths",
        "strength": "strengths",
        "weaknesses": "weaknesses",
        "weakness": "weaknesses",
        "opportunities": "opportunities",
        "opportunity": "opportunities",
        "threats": "threats",
        "threat": "threats",
    }

    for candidate in candidates:
        quadrant_raw = str(
            getattr(candidate, "quadrant", "")
        ).strip().lower()

        quadrant = quadrant_map.get(quadrant_raw)

        if quadrant is None:
            continue

        report[quadrant].append(
            {
                "title": getattr(
                    candidate, "title", ""
                ),
                "statement": getattr(
                    candidate, "statement", ""
                ),
                "rationale": getattr(
                    candidate, "rationale", ""
                ),
                "confidence": "low",
                "claim_strength": getattr(
                    candidate,
                    "claim_strength",
                    "directional_not_validated",
                ),
                "evidence_references": list(
                    getattr(
                        candidate,
                        "evidence_references",
                        (),
                    )
                ),
                "provisional": True,
            }
        )

    return report