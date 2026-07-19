
"""
Approved SWOT to Strategy Service

Converts one explicitly approved SWOT update into the input
contract consumed by Strategy Agent v1.

The service enforces the final Python-layer gate:

- Approval must be complete.
- The approved report must be ready for Strategy.
- No proposal candidate may remain unresolved.
- Only items marked should_feed_strategy_agent=True are included.
- manual_review_only items are excluded.
- Supporting signals and data gaps are never added to SWOT.
- Strategy receives validation_status=PASS only after these gates.
- No raw customer reviews are passed to Strategy.
- The service does not persist reports to MongoDB.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.agents.strategy import StrategyAgent
from app.services.approved_swot_builder import (
    ApprovedSwotItem,
    ApprovedSwotUpdate,
)


_QUADRANT_KEYS = {
    "strength": "strengths",
    "strengths": "strengths",
    "weakness": "weaknesses",
    "weaknesses": "weaknesses",
    "opportunity": "opportunities",
    "opportunities": "opportunities",
    "threat": "threats",
    "threats": "threats",
}


@dataclass(frozen=True, slots=True)
class ApprovedSwotStrategyResult:
    """Complete result of running Strategy from an approved SWOT."""

    business_id: UUID

    approved_report_id: UUID

    strategy_input: dict[str, Any]

    strategy_output: Any

    eligible_item_count: int

    excluded_item_count: int

    strategy_executed: bool

    source_coverage: tuple[str, ...]

    warnings: tuple[str, ...]


def _clean_text(
    value: Any,
    *,
    default: str,
) -> str:
    """Return stripped text with a deterministic fallback."""

    if isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        if cleaned:
            return cleaned

    return default


def _unique_strings(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    """Deduplicate non-empty strings while preserving order."""

    result: list[str] = []

    for value in values:
        if not isinstance(
            value,
            str,
        ):
            continue

        cleaned = value.strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    return tuple(
        result
    )


def _validate_approved_update(
    *,
    approved: ApprovedSwotUpdate,
    expected_business_id: UUID | None,
) -> None:
    """Reject incomplete or cross-business approved updates."""

    if (
        expected_business_id is not None
        and approved.business_id
        != expected_business_id
    ):
        raise ValueError(
            "Approved SWOT business_id does not match "
            "the expected business_id."
        )

    if not approved.approval_complete:
        raise ValueError(
            "Approved SWOT decisions are incomplete."
        )

    if approved.unresolved_candidate_ids:
        raise ValueError(
            "Approved SWOT contains unresolved candidates."
        )

    if not approved.ready_for_strategy:
        raise ValueError(
            "Approved SWOT is not ready for Strategy."
        )


def _eligible_items(
    approved: ApprovedSwotUpdate,
) -> tuple[
    ApprovedSwotItem,
    ...
]:
    """Return only explicitly Strategy-eligible approved items."""

    return tuple(
        item
        for item in approved.items
        if (
            item.should_feed_strategy_agent
            and not item.manual_review_only
        )
    )


def _quadrant_key(
    item: ApprovedSwotItem,
) -> str:
    """Return the Strategy SWOT-report key for one item."""

    normalized = _clean_text(
        item.quadrant,
        default="",
    ).lower()

    quadrant_key = _QUADRANT_KEYS.get(
        normalized
    )

    if quadrant_key is None:
        raise ValueError(
            "Approved SWOT item has an unsupported quadrant."
        )

    return quadrant_key


def _strategy_item(
    item: ApprovedSwotItem,
) -> dict[str, Any]:
    """
    Convert one approved item to the Strategy Agent contract.

    Safety and eligibility fields are taken from Python-controlled
    approved output, never from an LLM response.
    """

    return {
        "item_id": item.item_id,
        "quadrant": item.quadrant,
        "title": item.title,
        "reasoning": item.reasoning,
        "source_theme": (
            item.source_theme
        ),
        "tags": [],
        "claim_strength": (
            item.claim_strength
        ),
        "scoring": {
            "strategic_priority": (
                item.strategic_priority
            ),
            "confidence": (
                item.confidence
            ),
        },
        "evidence_refs": list(
            item.evidence_references
        ),
        "supporting_sources": list(
            item.supporting_sources
        ),
        "supporting_metrics": {
            key: value
            for key, value
            in item.supporting_metrics
        },
        "manual_review_only": False,
        "should_feed_strategy_agent": True,
        "origin": item.origin,
        "base_item_id": (
            item.base_item_id
        ),
        "source_candidate_id": (
            item.source_candidate_id
        ),
    }


def build_strategy_input_from_approved_swot(
    *,
    approved: ApprovedSwotUpdate,
    business_type: str | None,
    benchmark_quality: str = "unavailable",
    expected_business_id: UUID | None = None,
) -> dict[str, Any]:
    """
    Build a Strategy Agent-compatible SWOT payload.

    This function fails closed when approval is incomplete or when
    no approved item is eligible for Strategy.
    """

    _validate_approved_update(
        approved=approved,
        expected_business_id=(
            expected_business_id
        ),
    )

    eligible_items = _eligible_items(
        approved
    )

    if not eligible_items:
        raise ValueError(
            "Approved SWOT contains no Strategy-eligible items."
        )

    swot_report: dict[
        str,
        list[dict[str, Any]],
    ] = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    }

    for item in eligible_items:
        key = _quadrant_key(
            item
        )

        swot_report[key].append(
            _strategy_item(
                item
            )
        )

    normalized_benchmark_quality = (
        _clean_text(
            benchmark_quality,
            default="unavailable",
        ).lower()
    )

    if normalized_benchmark_quality not in {
        "high",
        "medium",
        "low",
        "unavailable",
    }:
        normalized_benchmark_quality = (
            "unavailable"
        )

    source_coverage = _unique_strings(
        approved.source_coverage
    )

    return {
        "business_id": str(
            approved.business_id
        ),
        "business_type": (
            _clean_text(
                business_type,
                default="unknown",
            )
        ),
        "engine_version": (
            approved.output_engine_version
        ),
        "swot_report": swot_report,
        "derived_opportunities": [],
        "directional_competitive_signals": [],
        "watchouts": [],
        "strategic_summary": {},
        "matrix_outputs": {
            "importance_performance_matrix": [],
            "opportunity_threat_matrix": [],
            "vulnerability_matrix": [],
        },
        "strategic_context": {
            "benchmark_quality": (
                normalized_benchmark_quality
            ),
            "source_coverage": list(
                source_coverage
            ),
            "approved_report_id": str(
                approved.approved_report_id
            ),
            "base_report_id": str(
                approved.base_report_id
            ),
            "source_proposal_id": str(
                approved.source_proposal_id
            ),
        },
        "quality_report": {
            "manual_review_needed": [],
            "low_confidence_items": [],
            "warnings": list(
                approved.warnings
            ),
        },
        "validation_results": {
            "overall_status": "PASS",
            "violations": [],
        },
        "meta": {
            "engine_version": (
                approved.output_engine_version
            ),
            "approved_report_id": str(
                approved.approved_report_id
            ),
            "base_report_id": str(
                approved.base_report_id
            ),
            "source_proposal_id": str(
                approved.source_proposal_id
            ),
            "approval_complete": (
                approved.approval_complete
            ),
            "ready_for_strategy": (
                approved.ready_for_strategy
            ),
            "source_coverage": list(
                source_coverage
            ),
        },
    }


def run_strategy_from_approved_swot(
    *,
    approved: ApprovedSwotUpdate,
    business_type: str | None,
    benchmark_quality: str = "unavailable",
    expected_business_id: UUID | None = None,
    strategy_agent: Any | None = None,
    llm_chain: Any | None = None,
    dry_run: bool = False,
) -> ApprovedSwotStrategyResult:
    """
    Build the approved SWOT payload and run Strategy Agent v1.

    A supplied strategy_agent is useful for deterministic tests.
    When omitted, the production StrategyAgent is constructed with
    the supplied LLM chain.
    """

    strategy_input = (
        build_strategy_input_from_approved_swot(
            approved=approved,
            business_type=business_type,
            benchmark_quality=(
                benchmark_quality
            ),
            expected_business_id=(
                expected_business_id
            ),
        )
    )

    effective_agent = (
        strategy_agent
        if strategy_agent is not None
        else StrategyAgent(
            llm_chain=(
                llm_chain
                or []
            ),
            dry_run=dry_run,
        )
    )

    run_method = getattr(
        effective_agent,
        "run",
        None,
    )

    if not callable(
        run_method
    ):
        raise TypeError(
            "The Strategy Agent must expose a callable "
            "run(swot_output) method."
        )

    strategy_output = run_method(
        strategy_input
    )

    eligible_count = sum(
        len(
            strategy_input[
                "swot_report"
            ][quadrant]
        )
        for quadrant in (
            "strengths",
            "weaknesses",
            "opportunities",
            "threats",
        )
    )

    excluded_count = (
        len(
            approved.items
        )
        - eligible_count
    )

    warnings = _unique_strings(
        approved.warnings
    )

    return ApprovedSwotStrategyResult(
        business_id=(
            approved.business_id
        ),
        approved_report_id=(
            approved.approved_report_id
        ),
        strategy_input=(
            strategy_input
        ),
        strategy_output=(
            strategy_output
        ),
        eligible_item_count=(
            eligible_count
        ),
        excluded_item_count=(
            excluded_count
        ),
        strategy_executed=True,
        source_coverage=(
            approved.source_coverage
        ),
        warnings=warnings,
    )