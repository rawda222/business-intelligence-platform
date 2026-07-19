"""
Strategy Generation Workflow Service

Loads the latest tenant-scoped approved SWOT report, restores the
approved domain contract, runs the Strategy Agent, and persists the
complete grounded Strategy output.

Only SWOT reports with all of the following may feed Strategy:

- status == "approved"
- approval_complete is True
- ready_for_strategy is True
- unresolved_candidate_ids is empty
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.agents.swot import LLMProvider
from app.agents.swot.llm.chain import (
    LLMClientFactory,
)
from app.services.approved_swot_builder import (
    ApprovedSwotItem,
    ApprovedSwotUpdate,
)
from app.services.approved_swot_strategy_service import (
    ApprovedSwotStrategyResult,
    run_strategy_from_approved_swot,
)
from app.services.swot_strategy_persistence_service import (
    get_latest_approved_swot_report,
    save_strategy_report,
)


_QUADRANT_NAMES = {
    "strengths": "strength",
    "weaknesses": "weakness",
    "opportunities": "opportunity",
    "threats": "threat",
}

_ALLOWED_ORIGINS = {
    "baseline",
    "retained_with_new_evidence",
    "approved_candidate",
    "accepted_conflict_candidate",
}


@dataclass(frozen=True, slots=True)
class StrategyGenerationWorkflowResult:
    """Complete result of one persisted Strategy generation."""

    business_id: UUID

    source_swot_report_id: UUID

    source_proposal_id: UUID | None

    approved_swot: ApprovedSwotUpdate

    strategy_result: ApprovedSwotStrategyResult

    strategy_output: Any

    persisted_strategy: Any


def _as_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    """Return one mapping-like value or fail closed."""

    if isinstance(
        value,
        Mapping,
    ):
        return dict(
            value
        )

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(
        model_dump
    ):
        dumped = model_dump(
            mode="python"
        )

        if isinstance(
            dumped,
            Mapping,
        ):
            return dict(
                dumped
            )

    raise ValueError(
        f"{field_name} must be a mapping."
    )


def _as_list(
    value: Any,
    *,
    field_name: str,
) -> list[Any]:
    """Return one list-like value or fail closed."""

    if isinstance(
        value,
        list,
    ):
        return list(
            value
        )

    if isinstance(
        value,
        tuple,
    ):
        return list(
            value
        )

    raise ValueError(
        f"{field_name} must be a list."
    )

    if isinstance(
        value,
        list,
    ):
        return list(
            value
        )

    if isinstance(
        value,
        tuple,
    ):
        return list(
            value
        )

    raise ValueError(
        f"{field_name} must be a list."
    )


def _uuid_value(
    value: Any,
    *,
    field_name: str,
    allow_none: bool = False,
) -> UUID | None:
    """Normalize one UUID or fail closed."""

    if value is None and allow_none:
        return None

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


def _required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    """Return one non-empty text value."""

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"{field_name} must be a string."
        )

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return cleaned


def _optional_text(
    value: Any,
    *,
    field_name: str,
) -> str | None:
    """Return one optional normalized string."""

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"{field_name} must be a string or null."
        )

    cleaned = value.strip()

    return cleaned or None


def _bool_value(
    value: Any,
    *,
    field_name: str,
) -> bool:
    """Require an explicit boolean value."""

    if not isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{field_name} must be a boolean."
        )

    return value


def _float_value(
    value: Any,
    *,
    field_name: str,
) -> float:
    """Normalize one numeric value."""

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{field_name} must be numeric."
        )

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"{field_name} must be numeric."
        ) from error


def _string_tuple(
    value: Any,
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Restore one ordered unique collection of strings."""

    values = _as_list(
        value,
        field_name=field_name,
    )

    result: list[str] = []

    for index, raw_value in enumerate(
        values
    ):
        cleaned = _required_text(
            raw_value,
            field_name=(
                f"{field_name}[{index}]"
            ),
        )

        if cleaned not in result:
            result.append(
                cleaned
            )

    return tuple(
        result
    )


def _supporting_metrics(
    value: Any,
    *,
    field_name: str,
) -> tuple[
    tuple[
        str,
        float | int | str,
    ],
    ...,
]:
    """Restore ordered supporting metric pairs."""

    values = _as_list(
        value,
        field_name=field_name,
    )

    result: list[
        tuple[
            str,
            float | int | str,
        ]
    ] = []

    for index, raw_pair in enumerate(
        values
    ):
        pair = _as_list(
            raw_pair,
            field_name=(
                f"{field_name}[{index}]"
            ),
        )

        if len(pair) != 2:
            raise ValueError(
                f"{field_name}[{index}] must "
                "contain exactly two values."
            )

        metric_name = _required_text(
            pair[0],
            field_name=(
                f"{field_name}[{index}][0]"
            ),
        )

        metric_value = pair[1]

        if (
            isinstance(
                metric_value,
                bool,
            )
            or not isinstance(
                metric_value,
                (
                    str,
                    int,
                    float,
                ),
            )
        ):
            raise ValueError(
                f"{field_name}[{index}][1] "
                "has an unsupported value."
            )

        result.append(
            (
                metric_name,
                metric_value,
            )
        )

    return tuple(
        result
    )


def _restore_approved_item(
    *,
    raw_item: Any,
    fallback_quadrant: str,
    field_name: str,
) -> ApprovedSwotItem:
    """Restore one approved SWOT item from Mongo-safe data."""

    item = _as_mapping(
        raw_item,
        field_name=field_name,
    )

    quadrant = item.get(
        "quadrant",
        fallback_quadrant,
    )

    quadrant = _required_text(
        quadrant,
        field_name=(
            f"{field_name}.quadrant"
        ),
    )

    if quadrant not in {
        "strength",
        "weakness",
        "opportunity",
        "threat",
    }:
        raise ValueError(
            f"{field_name}.quadrant is unsupported."
        )

    origin = _required_text(
        item.get(
            "origin"
        ),
        field_name=(
            f"{field_name}.origin"
        ),
    )

    if origin not in _ALLOWED_ORIGINS:
        raise ValueError(
            f"{field_name}.origin is unsupported."
        )

    return ApprovedSwotItem(
        item_id=_required_text(
            item.get(
                "item_id"
            ),
            field_name=(
                f"{field_name}.item_id"
            ),
        ),
        quadrant=quadrant,
        title=_required_text(
            item.get(
                "title"
            ),
            field_name=(
                f"{field_name}.title"
            ),
        ),
        reasoning=_required_text(
            item.get(
                "reasoning"
            ),
            field_name=(
                f"{field_name}.reasoning"
            ),
        ),
        source_theme=_optional_text(
            item.get(
                "source_theme"
            ),
            field_name=(
                f"{field_name}.source_theme"
            ),
        ),
        confidence=_float_value(
            item.get(
                "confidence"
            ),
            field_name=(
                f"{field_name}.confidence"
            ),
        ),
        strategic_priority=(
            _float_value(
                item.get(
                    "strategic_priority"
                ),
                field_name=(
                    f"{field_name}."
                    "strategic_priority"
                ),
            )
        ),
        claim_strength=_required_text(
            item.get(
                "claim_strength"
            ),
            field_name=(
                f"{field_name}.claim_strength"
            ),
        ),
        evidence_references=(
            _string_tuple(
                item.get(
                    "evidence_references",
                    [],
                ),
                field_name=(
                    f"{field_name}."
                    "evidence_references"
                ),
            )
        ),
        supporting_sources=(
            _string_tuple(
                item.get(
                    "supporting_sources",
                    [],
                ),
                field_name=(
                    f"{field_name}."
                    "supporting_sources"
                ),
            )
        ),
        supporting_metrics=(
            _supporting_metrics(
                item.get(
                    "supporting_metrics",
                    [],
                ),
                field_name=(
                    f"{field_name}."
                    "supporting_metrics"
                ),
            )
        ),
        should_feed_strategy_agent=(
            _bool_value(
                item.get(
                    "should_feed_strategy_agent"
                ),
                field_name=(
                    f"{field_name}."
                    "should_feed_strategy_agent"
                ),
            )
        ),
        manual_review_only=(
            _bool_value(
                item.get(
                    "manual_review_only"
                ),
                field_name=(
                    f"{field_name}."
                    "manual_review_only"
                ),
            )
        ),
        origin=origin,
        base_item_id=_optional_text(
            item.get(
                "base_item_id"
            ),
            field_name=(
                f"{field_name}.base_item_id"
            ),
        ),
        source_candidate_id=(
            _optional_text(
                item.get(
                    "source_candidate_id"
                ),
                field_name=(
                    f"{field_name}."
                    "source_candidate_id"
                ),
            )
        ),
    )


def restore_approved_swot_update(
    document: Any,
    *,
    expected_business_id: UUID,
) -> ApprovedSwotUpdate:
    """Restore the approved domain contract from one stored report."""

    document_business_id = _uuid_value(
        getattr(
            document,
            "business_id",
            None,
        ),
        field_name=(
            "approved SWOT business_id"
        ),
    )

    if document_business_id != expected_business_id:
        raise ValueError(
            "Approved SWOT business_id does not "
            "match the requested business_id."
        )

    if getattr(
        document,
        "status",
        None,
    ) != "approved":
        raise ValueError(
            "Strategy requires an approved SWOT report."
        )

    if not getattr(
        document,
        "approval_complete",
        False,
    ):
        raise ValueError(
            "Strategy requires complete SWOT approval."
        )

    if not getattr(
        document,
        "ready_for_strategy",
        False,
    ):
        raise ValueError(
            "SWOT report is not ready for Strategy."
        )

    unresolved_ids = tuple(
        getattr(
            document,
            "unresolved_candidate_ids",
            (),
        )
    )

    if unresolved_ids:
        raise ValueError(
            "Approved SWOT contains unresolved candidates."
        )

    swot_report = _as_mapping(
        getattr(
            document,
            "swot_report",
            None,
        ),
        field_name="approved SWOT swot_report",
    )

    items: list[
        ApprovedSwotItem
    ] = []

    for collection_name, quadrant in (
        _QUADRANT_NAMES.items()
    ):
        raw_items = _as_list(
            swot_report.get(
                collection_name,
                [],
            ),
            field_name=(
                "approved SWOT swot_report."
                f"{collection_name}"
            ),
        )

        for index, raw_item in enumerate(
            raw_items
        ):
            items.append(
                _restore_approved_item(
                    raw_item=raw_item,
                    fallback_quadrant=(
                        quadrant
                    ),
                    field_name=(
                        "approved SWOT "
                        f"{collection_name}"
                        f"[{index}]"
                    ),
                )
            )

    if not items:
        raise ValueError(
            "Approved SWOT contains no items."
        )

    report_id = _uuid_value(
        getattr(
            document,
            "report_id",
            None,
        ),
        field_name=(
            "approved SWOT report_id"
        ),
    )

    base_report_id = _uuid_value(
        getattr(
            document,
            "base_report_id",
            None,
        ),
        field_name=(
            "approved SWOT base_report_id"
        ),
    )

    source_proposal_id = _uuid_value(
        getattr(
            document,
            "source_proposal_id",
            None,
        ),
        field_name=(
            "approved SWOT source_proposal_id"
        ),
    )

    meta = getattr(
        document,
        "meta",
        {},
    )

    if not isinstance(
        meta,
        Mapping,
    ):
        meta = {}

    return ApprovedSwotUpdate(
        approved_report_id=report_id,
        business_id=document_business_id,
        base_report_id=base_report_id,
        source_proposal_id=(
            source_proposal_id
        ),
        base_engine_version=str(
            meta.get(
                "base_engine_version",
                "unknown",
            )
        ),
        output_engine_version=str(
            getattr(
                document,
                "engine_version",
                "8.0",
            )
        ),
        source_coverage=tuple(
            getattr(
                document,
                "source_coverage",
                (),
            )
        ),
        items=tuple(
            items
        ),
        approved_candidate_ids=tuple(
            getattr(
                document,
                "approved_candidate_ids",
                (),
            )
        ),
        rejected_candidate_ids=tuple(
            getattr(
                document,
                "rejected_candidate_ids",
                (),
            )
        ),
        unresolved_candidate_ids=(),
        supporting_signal_candidate_ids=tuple(
            meta.get(
                "supporting_signal_candidate_ids",
                (),
            )
        ),
        data_gap_candidate_ids=tuple(
            meta.get(
                "data_gap_candidate_ids",
                (),
            )
        ),
        warnings=tuple(
            meta.get(
                "warnings",
                (),
            )
        ),
        ready_for_strategy=True,
        approval_complete=True,
        version=str(
            meta.get(
                "version",
                "1.0",
            )
        ),
    )


async def generate_strategy_workflow(
    *,
    business_id: UUID,
    provider: LLMProvider = (
        LLMProvider.VERTEX_AI
    ),
    model: str = "gemini-2.5-flash",
    dry_run: bool = False,
    load_approved_fn: Any = (
        get_latest_approved_swot_report
    ),
    build_chain_fn: Any = (
        LLMClientFactory.build_chain
    ),
    run_strategy_fn: Any = (
        run_strategy_from_approved_swot
    ),
    save_strategy_fn: Any = (
        save_strategy_report
    ),
) -> StrategyGenerationWorkflowResult:
    """Generate and persist Strategy from the latest approved SWOT."""

    approved_document = await load_approved_fn(
        business_id=business_id,
    )

    if approved_document is None:
        raise ValueError(
            "No approved Strategy-ready SWOT report "
            "was found for this business."
        )

    approved = restore_approved_swot_update(
        approved_document,
        expected_business_id=business_id,
    )

    llm_chain = build_chain_fn(
        preferred=provider,
        model=model,
    )

    if not llm_chain:
        raise RuntimeError(
            "No Strategy LLM client could be initialized."
        )

    strategy_result = run_strategy_fn(
        approved=approved,
        business_type=(
            approved_document.business_type
        ),
        expected_business_id=business_id,
        llm_chain=llm_chain,
        dry_run=dry_run,
    )

    if not (
        strategy_result.strategy_executed
    ):
        raise ValueError(
            "Strategy generation did not execute."
        )

    strategy_output = (
        strategy_result.strategy_output
    )

    if strategy_output is None:
        raise ValueError(
            "Strategy generation returned no output."
        )

    persisted_strategy = (
        await save_strategy_fn(
            business_id=business_id,
            approved_swot=(
                approved_document
            ),
            strategy_output=(
                strategy_output
            ),
        )
    )

    persisted_business_id = _uuid_value(
        getattr(
            persisted_strategy,
            "business_id",
            None,
        ),
        field_name=(
            "persisted Strategy business_id"
        ),
    )

    if persisted_business_id != business_id:
        raise ValueError(
            "Persisted Strategy business_id does not "
            "match the requested business_id."
        )

    persisted_source_swot_id = (
        _uuid_value(
            getattr(
                persisted_strategy,
                "source_swot_id",
                None,
            ),
            field_name=(
                "persisted Strategy source_swot_id"
            ),
        )
    )

    if (
        persisted_source_swot_id
        != approved.approved_report_id
    ):
        raise ValueError(
            "Persisted Strategy source SWOT does not "
            "match the approved SWOT."
        )

    return StrategyGenerationWorkflowResult(
        business_id=business_id,
        source_swot_report_id=(
            approved.approved_report_id
        ),
        source_proposal_id=(
            approved.source_proposal_id
        ),
        approved_swot=approved,
        strategy_result=(
            strategy_result
        ),
        strategy_output=(
            strategy_output
        ),
        persisted_strategy=(
            persisted_strategy
        ),
    )