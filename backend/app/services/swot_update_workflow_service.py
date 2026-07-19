"""
SWOT Update Workflow Service

Orchestrates the complete production workflow for creating one
evidence-grounded draft SWOT update proposal.

The workflow:

1. Loads the latest stored SWOT baseline.
2. Normalizes the baseline conservatively.
3. Loads tenant-scoped cross-source customer voice.
4. Builds deterministic business trend intelligence.
5. Builds the Strong SWOT input bundle.
6. Runs grounded SWOT generation and validation.
7. Builds a human-reviewable draft proposal.
8. Persists the draft proposal.

This service never approves a proposal and never runs Strategy.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.services.ai_service import (
    get_latest_swot_report,
)
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
    build_grounded_swot_update_proposal,
)
from app.services.legacy_swot_adapter import (
    normalize_legacy_swot,
)
from app.services.strong_swot_input_service import (
    build_strong_swot_input,
)
from app.services.swot_strategy_persistence_service import (
    save_swot_update_proposal,
)


_DEFAULT_BASELINE_SOURCES = (
    "business_profile",
    "google_maps_reviews",
)


@dataclass(frozen=True, slots=True)
class SwotUpdateWorkflowResult:
    """Complete result of creating one persisted draft proposal."""

    business_id: UUID

    baseline_report_id: UUID

    normalized_baseline: Any

    customer_voice: Any

    trend_report: Any

    trend_intelligence: Any

    strong_swot_bundle: Any

    generation: Any

    grounded_proposal: Any

    persisted_proposal: Any

    proposal_id: UUID

    source_coverage: tuple[str, ...]

    warnings: tuple[str, ...]


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


def _source_coverage(
    baseline_document: Any,
) -> tuple[str, ...]:
    """Read baseline source coverage with a conservative fallback."""

    raw_sources = getattr(
        baseline_document,
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


async def create_swot_update_proposal_workflow(
    *,
    business_id: UUID,
    business_name: str,
    business_type: str | None,
    range_start: datetime,
    range_end: datetime,
    review_source: str = "google_maps",
    max_engagement_curves: int = 5,
    load_baseline_fn: Any = get_latest_swot_report,
    normalize_baseline_fn: Any = normalize_legacy_swot,
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
    build_proposal_fn: Any = (
        build_grounded_swot_update_proposal
    ),
    save_proposal_fn: Any = (
        save_swot_update_proposal
    ),
) -> SwotUpdateWorkflowResult:
    """
    Create and persist one grounded draft SWOT update proposal.

    Dependencies are injectable so the workflow can be tested without
    MongoDB, PostgreSQL, or Vertex AI.
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

    baseline_document = await load_baseline_fn(
        business_id=business_id,
    )

    if baseline_document is None:
        raise ValueError(
            "A stored SWOT baseline is required before "
            "creating an update proposal."
        )

    baseline_business_id = _uuid_value(
        getattr(
            baseline_document,
            "business_id",
            None,
        ),
        field_name=(
            "baseline business_id"
        ),
    )

    if baseline_business_id != business_id:
        raise ValueError(
            "Stored SWOT baseline business_id does not "
            "match the requested business_id."
        )

    baseline_report_id = _uuid_value(
        getattr(
            baseline_document,
            "report_id",
            None,
        ),
        field_name=(
            "baseline report_id"
        ),
    )

    baseline_engine_version = str(
        getattr(
            baseline_document,
            "engine_version",
            "unknown",
        )
        or "unknown"
    )

    baseline = normalize_baseline_fn(
        business_id=business_id,
        report_id=baseline_report_id,
        engine_version=(
            baseline_engine_version
        ),
        swot_report=getattr(
            baseline_document,
            "swot_report",
            {},
        ),
        source_coverage=_source_coverage(
            baseline_document
        ),
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

    grounded_proposal = (
        build_proposal_fn(
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
            "Grounded SWOT result is not safe for "
            "the approval workflow."
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

    return SwotUpdateWorkflowResult(
        business_id=business_id,
        baseline_report_id=(
            baseline_report_id
        ),
        normalized_baseline=baseline,
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