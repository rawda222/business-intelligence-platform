"""
SWOT Approval Workflow Service

Reconstructs persisted draft proposal snapshots, applies explicit
human approval decisions, persists the approved SWOT report, and
marks the source proposal as approved.

The workflow never runs Strategy. Strategy remains a separate
operation that consumes only an approved, Strategy-ready SWOT.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.services.approved_swot_builder import (
    ApprovedSwotUpdate,
    SwotProposalApprovalDecision,
    build_approved_swot_update,
)
from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
    NormalizedSwotItem,
)
from app.services.swot_strategy_persistence_service import (
    get_swot_update_proposal,
    mark_proposal_approved,
    save_approved_swot_report,
)
from app.services.swot_update_proposal_service import (
    SwotUpdateProposal,
    SwotUpdateProposalItem,
)


@dataclass(frozen=True, slots=True)
class SwotApprovalWorkflowResult:
    """Complete result of approving one persisted draft proposal."""

    business_id: UUID

    proposal_id: UUID

    approved_report_id: UUID

    baseline: NormalizedSwotBaseline

    proposal: SwotUpdateProposal

    decisions: tuple[
        SwotProposalApprovalDecision,
        ...
    ]

    approved_update: ApprovedSwotUpdate

    approved_report: Any

    persisted_proposal: Any


def _as_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    """Return a plain mapping or fail closed."""

    if isinstance(
        value,
        Mapping,
    ):
        return dict(
            value
        )

    raise ValueError(
        f"{field_name} must be a mapping."
    )


def _as_list(
    value: Any,
    *,
    field_name: str,
) -> list[Any]:
    """Return a list-like value or fail closed."""

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


def _required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    """Return one non-empty string or fail closed."""

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


def _float_value(
    value: Any,
    *,
    field_name: str,
) -> float:
    """Normalize one numeric field."""

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


def _string_tuple(
    value: Any,
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Normalize an ordered collection of unique strings."""

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
    """Restore serialized supporting metric pairs."""

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


def restore_normalized_swot_baseline(
    snapshot: Any,
) -> NormalizedSwotBaseline:
    """Restore one trusted baseline snapshot conservatively."""

    data = _as_mapping(
        snapshot,
        field_name="baseline_snapshot",
    )

    raw_items = _as_list(
        data.get(
            "items",
            [],
        ),
        field_name="baseline_snapshot.items",
    )

    items: list[
        NormalizedSwotItem
    ] = []

    for index, raw_item in enumerate(
        raw_items
    ):
        item = _as_mapping(
            raw_item,
            field_name=(
                "baseline_snapshot."
                f"items[{index}]"
            ),
        )

        quadrant = _required_text(
            item.get(
                "quadrant"
            ),
            field_name=(
                "baseline_snapshot."
                f"items[{index}].quadrant"
            ),
        )

        if quadrant not in {
            "strength",
            "weakness",
            "opportunity",
            "threat",
        }:
            raise ValueError(
                "Baseline item has an "
                "unsupported quadrant."
            )

        claim_strength = _required_text(
            item.get(
                "claim_strength"
            ),
            field_name=(
                "baseline_snapshot."
                f"items[{index}].claim_strength"
            ),
        )

        if claim_strength not in {
            "validated",
            "internally_supported",
            "directional_not_validated",
            "early_warning",
        }:
            raise ValueError(
                "Baseline item has an unsupported "
                "claim_strength."
            )

        items.append(
            NormalizedSwotItem(
                item_id=_required_text(
                    item.get(
                        "item_id"
                    ),
                    field_name=(
                        "baseline_snapshot."
                        f"items[{index}].item_id"
                    ),
                ),
                item_id_was_generated=(
                    _bool_value(
                        item.get(
                            "item_id_was_generated"
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
                            "item_id_was_generated"
                        ),
                    )
                ),
                quadrant=quadrant,
                title=_required_text(
                    item.get(
                        "title"
                    ),
                    field_name=(
                        "baseline_snapshot."
                        f"items[{index}].title"
                    ),
                ),
                reasoning=_required_text(
                    item.get(
                        "reasoning"
                    ),
                    field_name=(
                        "baseline_snapshot."
                        f"items[{index}].reasoning"
                    ),
                ),
                source_theme=_optional_text(
                    item.get(
                        "source_theme"
                    ),
                    field_name=(
                        "baseline_snapshot."
                        f"items[{index}].source_theme"
                    ),
                ),
                confidence=_float_value(
                    item.get(
                        "confidence"
                    ),
                    field_name=(
                        "baseline_snapshot."
                        f"items[{index}].confidence"
                    ),
                ),
                strategic_priority=(
                    _float_value(
                        item.get(
                            "strategic_priority"
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
                            "strategic_priority"
                        ),
                    )
                ),
                claim_strength=(
                    claim_strength
                ),
                source_should_feed_strategy_agent=(
                    _bool_value(
                        item.get(
                            "source_should_feed_strategy_agent"
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
                            "source_should_feed_strategy_agent"
                        ),
                    )
                ),
                should_feed_strategy_agent=(
                    _bool_value(
                        item.get(
                            "should_feed_strategy_agent"
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
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
                            "baseline_snapshot."
                            f"items[{index}]."
                            "manual_review_only"
                        ),
                    )
                ),
                evidence_references=(
                    _string_tuple(
                        item.get(
                            "evidence_references",
                            [],
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
                            "evidence_references"
                        ),
                    )
                ),
                normalization_warnings=(
                    _string_tuple(
                        item.get(
                            "normalization_warnings",
                            [],
                        ),
                        field_name=(
                            "baseline_snapshot."
                            f"items[{index}]."
                            "normalization_warnings"
                        ),
                    )
                ),
            )
        )

    return NormalizedSwotBaseline(
        business_id=_uuid_value(
            data.get(
                "business_id"
            ),
            field_name=(
                "baseline_snapshot.business_id"
            ),
        ),
        report_id=_uuid_value(
            data.get(
                "report_id"
            ),
            field_name=(
                "baseline_snapshot.report_id"
            ),
        ),
        engine_version=_required_text(
            data.get(
                "engine_version"
            ),
            field_name=(
                "baseline_snapshot.engine_version"
            ),
        ),
        source_coverage=_string_tuple(
            data.get(
                "source_coverage",
                [],
            ),
            field_name=(
                "baseline_snapshot.source_coverage"
            ),
        ),
        items=tuple(
            items
        ),
        warnings=_string_tuple(
            data.get(
                "warnings",
                [],
            ),
            field_name=(
                "baseline_snapshot.warnings"
            ),
        ),
    )


def _restore_proposal_item(
    value: Any,
    *,
    index: int,
) -> SwotUpdateProposalItem:
    """Restore one persisted proposal item."""

    item = _as_mapping(
        value,
        field_name=(
            f"proposal_snapshot.items[{index}]"
        ),
    )

    decision = _required_text(
        item.get(
            "decision"
        ),
        field_name=(
            "proposal_snapshot."
            f"items[{index}].decision"
        ),
    )

    if decision not in {
        "add",
        "retain_with_new_evidence",
        "conflict_requires_review",
        "ignore_supporting_signal",
        "ignore_data_gap",
    }:
        raise ValueError(
            "Proposal item has an "
            "unsupported decision."
        )

    quadrant = _optional_text(
        item.get(
            "quadrant"
        ),
        field_name=(
            "proposal_snapshot."
            f"items[{index}].quadrant"
        ),
    )

    matched_quadrant = _optional_text(
        item.get(
            "matched_baseline_quadrant"
        ),
        field_name=(
            "proposal_snapshot."
            f"items[{index}]."
            "matched_baseline_quadrant"
        ),
    )

    valid_quadrants = {
        "strength",
        "weakness",
        "opportunity",
        "threat",
    }

    if (
        quadrant is not None
        and quadrant not in valid_quadrants
    ):
        raise ValueError(
            "Proposal item has an "
            "unsupported quadrant."
        )

    if (
        matched_quadrant is not None
        and matched_quadrant
        not in valid_quadrants
    ):
        raise ValueError(
            "Proposal item has an unsupported "
            "matched baseline quadrant."
        )

    return SwotUpdateProposalItem(
        decision=decision,
        candidate_id=_required_text(
            item.get(
                "candidate_id"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].candidate_id"
            ),
        ),
        quadrant=quadrant,
        matched_baseline_item_id=(
            _optional_text(
                item.get(
                    "matched_baseline_item_id"
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "matched_baseline_item_id"
                ),
            )
        ),
        matched_baseline_quadrant=(
            matched_quadrant
        ),
        title=_required_text(
            item.get(
                "title"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].title"
            ),
        ),
        statement=_required_text(
            item.get(
                "statement"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].statement"
            ),
        ),
        rationale=_required_text(
            item.get(
                "rationale"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].rationale"
            ),
        ),
        confidence=_float_value(
            item.get(
                "confidence"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].confidence"
            ),
        ),
        claim_strength=_required_text(
            item.get(
                "claim_strength"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].claim_strength"
            ),
        ),
        evidence_references=(
            _string_tuple(
                item.get(
                    "evidence_references",
                    [],
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "evidence_references"
                ),
            )
        ),
        supporting_sources=_string_tuple(
            item.get(
                "supporting_sources",
                [],
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}]."
                "supporting_sources"
            ),
        ),
        supporting_metrics=(
            _supporting_metrics(
                item.get(
                    "supporting_metrics",
                    [],
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "supporting_metrics"
                ),
            )
        ),
        mapping_rule=_required_text(
            item.get(
                "mapping_rule"
            ),
            field_name=(
                "proposal_snapshot."
                f"items[{index}].mapping_rule"
            ),
        ),
        eligible_for_strategy_after_approval=(
            _bool_value(
                item.get(
                    "eligible_for_strategy_after_approval"
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "eligible_for_strategy_after_approval"
                ),
            )
        ),
        should_feed_strategy_agent=(
            _bool_value(
                item.get(
                    "should_feed_strategy_agent"
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "should_feed_strategy_agent"
                ),
            )
        ),
        requires_manual_review=(
            _bool_value(
                item.get(
                    "requires_manual_review"
                ),
                field_name=(
                    "proposal_snapshot."
                    f"items[{index}]."
                    "requires_manual_review"
                ),
            )
        ),
    )


def restore_swot_update_proposal(
    snapshot: Any,
) -> SwotUpdateProposal:
    """Restore one persisted draft proposal snapshot."""

    data = _as_mapping(
        snapshot,
        field_name="proposal_snapshot",
    )

    raw_items = _as_list(
        data.get(
            "items",
            [],
        ),
        field_name="proposal_snapshot.items",
    )

    items = tuple(
        _restore_proposal_item(
            raw_item,
            index=index,
        )
        for index, raw_item in enumerate(
            raw_items
        )
    )

    return SwotUpdateProposal(
        proposal_id=_uuid_value(
            data.get(
                "proposal_id"
            ),
            field_name=(
                "proposal_snapshot.proposal_id"
            ),
        ),
        business_id=_uuid_value(
            data.get(
                "business_id"
            ),
            field_name=(
                "proposal_snapshot.business_id"
            ),
        ),
        base_report_id=_uuid_value(
            data.get(
                "base_report_id"
            ),
            field_name=(
                "proposal_snapshot.base_report_id"
            ),
        ),
        base_engine_version=(
            _required_text(
                data.get(
                    "base_engine_version"
                ),
                field_name=(
                    "proposal_snapshot."
                    "base_engine_version"
                ),
            )
        ),
        status=_required_text(
            data.get(
                "status"
            ),
            field_name=(
                "proposal_snapshot.status"
            ),
        ),
        baseline_sources=_string_tuple(
            data.get(
                "baseline_sources",
                [],
            ),
            field_name=(
                "proposal_snapshot."
                "baseline_sources"
            ),
        ),
        current_sources=_string_tuple(
            data.get(
                "current_sources",
                [],
            ),
            field_name=(
                "proposal_snapshot.current_sources"
            ),
        ),
        new_sources_since_baseline=(
            _string_tuple(
                data.get(
                    "new_sources_since_baseline",
                    [],
                ),
                field_name=(
                    "proposal_snapshot."
                    "new_sources_since_baseline"
                ),
            )
        ),
        items=items,
        add_items=tuple(
            item
            for item in items
            if item.decision == "add"
        ),
        retained_items=tuple(
            item
            for item in items
            if (
                item.decision
                == "retain_with_new_evidence"
            )
        ),
        conflict_items=tuple(
            item
            for item in items
            if (
                item.decision
                == "conflict_requires_review"
            )
        ),
        supporting_signals=tuple(
            item
            for item in items
            if (
                item.decision
                == "ignore_supporting_signal"
            )
        ),
        data_gaps=tuple(
            item
            for item in items
            if (
                item.decision
                == "ignore_data_gap"
            )
        ),
        unchanged_baseline_item_ids=(
            _string_tuple(
                data.get(
                    "unchanged_baseline_item_ids",
                    [],
                ),
                field_name=(
                    "proposal_snapshot."
                    "unchanged_baseline_item_ids"
                ),
            )
        ),
        warnings=_string_tuple(
            data.get(
                "warnings",
                [],
            ),
            field_name=(
                "proposal_snapshot.warnings"
            ),
        ),
        requires_human_approval=(
            _bool_value(
                data.get(
                    "requires_human_approval"
                ),
                field_name=(
                    "proposal_snapshot."
                    "requires_human_approval"
                ),
            )
        ),
        proposal_version=_required_text(
            data.get(
                "proposal_version",
                "1.0",
            ),
            field_name=(
                "proposal_snapshot.proposal_version"
            ),
        ),
    )


def build_approval_decisions(
    values: tuple[
        Mapping[str, Any],
        ...
    ],
) -> tuple[
    SwotProposalApprovalDecision,
    ...
]:
    """Build explicit typed approval decisions."""

    allowed_decisions = {
        "approve",
        "reject",
        "keep_baseline",
        "accept_candidate",
    }

    result: list[
        SwotProposalApprovalDecision
    ] = []

    for index, raw_value in enumerate(
        values
    ):
        value = _as_mapping(
            raw_value,
            field_name=(
                f"decisions[{index}]"
            ),
        )

        decision = _required_text(
            value.get(
                "decision"
            ),
            field_name=(
                f"decisions[{index}].decision"
            ),
        )

        if decision not in allowed_decisions:
            raise ValueError(
                f"Unsupported approval decision "
                f"'{decision}'."
            )

        result.append(
            SwotProposalApprovalDecision(
                candidate_id=_required_text(
                    value.get(
                        "candidate_id"
                    ),
                    field_name=(
                        f"decisions[{index}]."
                        "candidate_id"
                    ),
                ),
                decision=decision,
            )
        )

    return tuple(
        result
    )


async def approve_swot_update_proposal_workflow(
    *,
    business_id: UUID,
    proposal_id: UUID,
    business_type: str,
    decision_values: tuple[
        Mapping[str, Any],
        ...
    ],
    load_proposal_fn: Any = (
        get_swot_update_proposal
    ),
    build_approved_fn: Any = (
        build_approved_swot_update
    ),
    save_approved_fn: Any = (
        save_approved_swot_report
    ),
    mark_approved_fn: Any = (
        mark_proposal_approved
    ),
) -> SwotApprovalWorkflowResult:
    """Approve and persist one tenant-scoped draft proposal."""

    document = await load_proposal_fn(
        business_id=business_id,
        proposal_id=proposal_id,
    )

    if document is None:
        raise ValueError(
            "SWOT update proposal was not found."
        )

    if document.status != "draft":
        raise ValueError(
            "Only draft SWOT update proposals "
            "may be approved."
        )

    document_business_id = _uuid_value(
        document.business_id,
        field_name="document business_id",
    )

    document_proposal_id = _uuid_value(
        document.proposal_id,
        field_name="document proposal_id",
    )

    if document_business_id != business_id:
        raise ValueError(
            "Proposal business_id does not match "
            "the requested business_id."
        )

    if document_proposal_id != proposal_id:
        raise ValueError(
            "Proposal ID does not match the "
            "requested proposal_id."
        )

    if document.baseline_snapshot is None:
        baseline = NormalizedSwotBaseline(
            business_id=business_id,
            report_id=None,
            engine_version="genesis",
            source_coverage=(),
            items=(),
            warnings=(),
        )
    else:
        baseline = (
            restore_normalized_swot_baseline(
                document.baseline_snapshot
            )
        )

    proposal = restore_swot_update_proposal(
        document.proposal_snapshot
    )

    if baseline.business_id != business_id:
        raise ValueError(
            "Baseline snapshot business_id does "
            "not match the requested business_id."
        )

    if proposal.business_id != business_id:
        raise ValueError(
            "Proposal snapshot business_id does "
            "not match the requested business_id."
        )

    if proposal.proposal_id != proposal_id:
        raise ValueError(
            "Proposal snapshot ID does not match "
            "the requested proposal_id."
        )

    if (
        baseline.report_id
        != proposal.base_report_id
    ):
        raise ValueError(
            "Proposal snapshot does not match "
            "the persisted baseline snapshot."
        )

    decisions = build_approval_decisions(
        decision_values
    )

    approved_update = build_approved_fn(
        baseline=baseline,
        proposal=proposal,
        decisions=decisions,
    )

    if not approved_update.approval_complete:
        raise ValueError(
            "Approval decisions are incomplete."
        )

    if (
        approved_update
        .unresolved_candidate_ids
    ):
        raise ValueError(
            "Approval contains unresolved candidates."
        )

    approved_report = await save_approved_fn(
        approved=approved_update,
        business_type=business_type,
    )

    persisted_proposal = await (
        mark_approved_fn(
            document=document,
            decisions=decisions,
            approved_report_id=(
                approved_update
                .approved_report_id
            ),
        )
    )

    return SwotApprovalWorkflowResult(
        business_id=business_id,
        proposal_id=proposal_id,
        approved_report_id=(
            approved_update
            .approved_report_id
        ),
        baseline=baseline,
        proposal=proposal,
        decisions=decisions,
        approved_update=approved_update,
        approved_report=approved_report,
        persisted_proposal=(
            persisted_proposal
        ),
    )
