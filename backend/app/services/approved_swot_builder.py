"""
Approved SWOT Builder

Applies explicit human approval decisions to a draft SWOT update
proposal and produces a versioned, evidence-backed SWOT result.

The builder is deterministic and pure:

- It does not call an LLM.
- It does not write to MongoDB.
- It does not approve draft items implicitly.
- It preserves unmatched baseline items.
- It does not allow unresolved conflicts into Strategy.
- Human approval cannot bypass the evidence quality gate.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5

from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
    NormalizedSwotItem,
)
from app.services.swot_update_proposal_service import (
    SwotUpdateProposal,
    SwotUpdateProposalItem,
)


ApprovalDecision = Literal[
    "approve",
    "reject",
    "keep_baseline",
    "accept_candidate",
]

ApprovedItemOrigin = Literal[
    "baseline",
    "retained_with_new_evidence",
    "approved_candidate",
    "accepted_conflict_candidate",
]


_APPROVED_REPORT_NAMESPACE = UUID(
    "99999999-9999-9999-9999-999999999999"
)

_APPROVED_ITEM_NAMESPACE = UUID(
    "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
)


@dataclass(frozen=True, slots=True)
class SwotProposalApprovalDecision:
    """One explicit decision for one proposal candidate."""

    candidate_id: str

    decision: ApprovalDecision


@dataclass(frozen=True, slots=True)
class ApprovedSwotItem:
    """One item in the approved evidence-backed SWOT."""

    item_id: str

    quadrant: str

    title: str

    reasoning: str

    source_theme: str | None

    confidence: float

    strategic_priority: float

    claim_strength: str

    evidence_references: tuple[
        str,
        ...
    ]

    supporting_sources: tuple[
        str,
        ...
    ]

    supporting_metrics: tuple[
        tuple[
            str,
            float | int | str,
        ],
        ...
    ]

    should_feed_strategy_agent: bool

    manual_review_only: bool

    origin: ApprovedItemOrigin

    base_item_id: str | None

    source_candidate_id: str | None


@dataclass(frozen=True, slots=True)
class ApprovedSwotUpdate:
    """Result of applying approval decisions to one draft proposal."""

    approved_report_id: UUID

    business_id: UUID

    base_report_id: UUID

    source_proposal_id: UUID

    base_engine_version: str

    output_engine_version: str

    source_coverage: tuple[
        str,
        ...
    ]

    items: tuple[
        ApprovedSwotItem,
        ...
    ]

    approved_candidate_ids: tuple[
        str,
        ...
    ]

    rejected_candidate_ids: tuple[
        str,
        ...
    ]

    unresolved_candidate_ids: tuple[
        str,
        ...
    ]

    supporting_signal_candidate_ids: tuple[
        str,
        ...
    ]

    data_gap_candidate_ids: tuple[
        str,
        ...
    ]

    warnings: tuple[
        str,
        ...
    ]

    ready_for_strategy: bool

    approval_complete: bool

    version: str = "1.0"


def _unique_strings(
    *groups: tuple[
        str,
        ...
    ],
) -> tuple[
    str,
    ...
]:
    """Deduplicate strings while preserving their order."""

    result: list[str] = []

    for group in groups:
        for value in group:
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


def _decision_map(
    decisions: tuple[
        SwotProposalApprovalDecision,
        ...
    ],
) -> dict[
    str,
    ApprovalDecision,
]:
    """Validate and index explicit approval decisions."""

    result: dict[
        str,
        ApprovalDecision
    ] = {}

    for decision in decisions:
        candidate_id = (
            decision.candidate_id.strip()
        )

        if not candidate_id:
            raise ValueError(
                "Approval candidate_id cannot be empty."
            )

        if candidate_id in result:
            raise ValueError(
                "Duplicate approval decision for "
                f"candidate_id '{candidate_id}'."
            )

        result[candidate_id] = (
            decision.decision
        )

    return result


def _validate_inputs(
    *,
    baseline: NormalizedSwotBaseline,
    proposal: SwotUpdateProposal,
) -> None:
    """Validate baseline and proposal identity."""

    if (
        proposal.business_id
        != baseline.business_id
    ):
        raise ValueError(
            "SWOT proposal business_id does not "
            "match the baseline business_id."
        )

    if (
        proposal.base_report_id
        != baseline.report_id
    ):
        raise ValueError(
            "SWOT proposal base_report_id does not "
            "match the baseline report_id."
        )

    if proposal.status != "draft":
        raise ValueError(
            "Only draft SWOT proposals can be "
            "applied by the approval builder."
        )


def _validate_decision_targets(
    *,
    proposal: SwotUpdateProposal,
    decisions_by_candidate: dict[
        str,
        ApprovalDecision,
    ],
) -> None:
    """Reject decisions that target unknown or ignored candidates."""

    actionable_ids = {
        item.candidate_id
        for item in proposal.items
        if item.decision
        in {
            "add",
            "retain_with_new_evidence",
            "conflict_requires_review",
        }
    }

    for candidate_id in decisions_by_candidate:
        if candidate_id not in actionable_ids:
            raise ValueError(
                "Approval decision targets an "
                "unknown or non-actionable "
                f"candidate_id '{candidate_id}'."
            )


def _validate_decision_for_item(
    *,
    item: SwotUpdateProposalItem,
    decision: ApprovalDecision,
) -> None:
    """Ensure a decision is compatible with the proposal item."""

    allowed: dict[
        str,
        set[
            ApprovalDecision
        ],
    ] = {
        "add": {
            "approve",
            "reject",
        },
        "retain_with_new_evidence": {
            "approve",
            "reject",
        },
        "conflict_requires_review": {
            "keep_baseline",
            "accept_candidate",
        },
    }

    allowed_decisions = allowed.get(
        item.decision,
        set(),
    )

    if decision not in allowed_decisions:
        raise ValueError(
            f"Decision '{decision}' is not valid "
            f"for proposal decision '{item.decision}'."
        )


def _baseline_item_to_approved(
    item: NormalizedSwotItem,
) -> ApprovedSwotItem:
    """Preserve one normalized baseline item."""

    return ApprovedSwotItem(
        item_id=item.item_id,
        quadrant=item.quadrant,
        title=item.title,
        reasoning=item.reasoning,
        source_theme=item.source_theme,
        confidence=item.confidence,
        strategic_priority=(
            item.strategic_priority
        ),
        claim_strength=(
            item.claim_strength
        ),
        evidence_references=(
            item.evidence_references
        ),
        supporting_sources=(),
        supporting_metrics=(),
        should_feed_strategy_agent=(
            item.should_feed_strategy_agent
        ),
        manual_review_only=(
            item.manual_review_only
        ),
        origin="baseline",
        base_item_id=item.item_id,
        source_candidate_id=None,
    )


def _approved_candidate_item_id(
    *,
    proposal: SwotUpdateProposal,
    item: SwotUpdateProposalItem,
) -> str:
    """Build a deterministic ID for an approved candidate."""

    identity = (
        f"{proposal.proposal_id}:"
        f"{item.candidate_id}:"
        f"{item.quadrant}"
    )

    generated_id = uuid5(
        _APPROVED_ITEM_NAMESPACE,
        identity,
    )

    return (
        "trend:"
        f"{generated_id}"
    )


def _proposal_item_to_approved(
    *,
    proposal: SwotUpdateProposal,
    item: SwotUpdateProposalItem,
    origin: ApprovedItemOrigin,
) -> ApprovedSwotItem:
    """Create an approved SWOT item from one candidate."""

    if item.quadrant is None:
        raise ValueError(
            "An approved SWOT candidate must have "
            "a quadrant."
        )

    strategy_eligible = (
        item
        .eligible_for_strategy_after_approval
    )

    return ApprovedSwotItem(
        item_id=(
            _approved_candidate_item_id(
                proposal=proposal,
                item=item,
            )
        ),
        quadrant=item.quadrant,
        title=item.title,
        reasoning=(
            item.rationale
        ),
        source_theme=(
            item.mapping_rule
        ),
        confidence=item.confidence,
        strategic_priority=0.0,
        claim_strength=(
            item.claim_strength
        ),
        evidence_references=(
            item.evidence_references
        ),
        supporting_sources=(
            item.supporting_sources
        ),
        supporting_metrics=(
            item.supporting_metrics
        ),
        should_feed_strategy_agent=(
            strategy_eligible
        ),
        manual_review_only=(
            not strategy_eligible
        ),
        origin=origin,
        base_item_id=(
            item.matched_baseline_item_id
        ),
        source_candidate_id=(
            item.candidate_id
        ),
    )


def _retained_item_with_evidence(
    *,
    baseline_item: NormalizedSwotItem,
    proposal_item: SwotUpdateProposalItem,
) -> ApprovedSwotItem:
    """Retain a baseline item and attach approved new evidence."""

    strategy_eligible = (
        proposal_item
        .eligible_for_strategy_after_approval
    )

    return ApprovedSwotItem(
        item_id=baseline_item.item_id,
        quadrant=baseline_item.quadrant,
        title=baseline_item.title,
        reasoning=baseline_item.reasoning,
        source_theme=(
            baseline_item.source_theme
        ),
        confidence=max(
            baseline_item.confidence,
            proposal_item.confidence,
        ),
        strategic_priority=(
            baseline_item
            .strategic_priority
        ),
        claim_strength=(
            proposal_item.claim_strength
            if strategy_eligible
            else baseline_item.claim_strength
        ),
        evidence_references=(
            _unique_strings(
                baseline_item
                .evidence_references,
                proposal_item
                .evidence_references,
            )
        ),
        supporting_sources=(
            proposal_item
            .supporting_sources
        ),
        supporting_metrics=(
            proposal_item
            .supporting_metrics
        ),
        should_feed_strategy_agent=(
            strategy_eligible
        ),
        manual_review_only=(
            not strategy_eligible
        ),
        origin=(
            "retained_with_new_evidence"
        ),
        base_item_id=(
            baseline_item.item_id
        ),
        source_candidate_id=(
            proposal_item.candidate_id
        ),
    )


def _approved_report_id(
    *,
    proposal: SwotUpdateProposal,
    decisions: tuple[
        SwotProposalApprovalDecision,
        ...
    ],
) -> UUID:
    """Build a deterministic approved report identifier."""

    sorted_decisions = sorted(
        decisions,
        key=lambda decision: (
            decision.candidate_id,
            decision.decision,
        ),
    )

    decision_identity = "|".join(
        (
            f"{decision.candidate_id}:"
            f"{decision.decision}"
        )
        for decision in sorted_decisions
    )

    identity = (
        f"{proposal.proposal_id}:"
        f"{decision_identity}"
    )

    return uuid5(
        _APPROVED_REPORT_NAMESPACE,
        identity,
    )


def build_approved_swot_update(
    *,
    baseline: NormalizedSwotBaseline,
    proposal: SwotUpdateProposal,
    decisions: tuple[
        SwotProposalApprovalDecision,
        ...
    ],
) -> ApprovedSwotUpdate:
    """
    Apply explicit decisions to one draft SWOT update proposal.

    Draft proposal items never feed Strategy directly. Strategy
    eligibility is enabled only in this approved output and only
    when the evidence gate marked the item eligible after approval.
    """

    _validate_inputs(
        baseline=baseline,
        proposal=proposal,
    )

    decisions_by_candidate = (
        _decision_map(
            decisions
        )
    )

    _validate_decision_targets(
        proposal=proposal,
        decisions_by_candidate=(
            decisions_by_candidate
        ),
    )

    baseline_by_id = {
        item.item_id: item
        for item in baseline.items
    }

    output_by_item_id = {
        item.item_id: (
            _baseline_item_to_approved(
                item
            )
        )
        for item in baseline.items
    }

    approved_candidate_ids: list[str] = []

    rejected_candidate_ids: list[str] = []

    unresolved_candidate_ids: list[str] = []

    for proposal_item in proposal.items:
        if proposal_item.decision in {
            "ignore_supporting_signal",
            "ignore_data_gap",
        }:
            continue

        explicit_decision = (
            decisions_by_candidate.get(
                proposal_item.candidate_id
            )
        )

        if explicit_decision is None:
            unresolved_candidate_ids.append(
                proposal_item.candidate_id
            )

            continue

        _validate_decision_for_item(
            item=proposal_item,
            decision=explicit_decision,
        )

        if explicit_decision == "reject":
            rejected_candidate_ids.append(
                proposal_item.candidate_id
            )

            continue

        if explicit_decision == "keep_baseline":
            rejected_candidate_ids.append(
                proposal_item.candidate_id
            )

            continue

        if (
            proposal_item.decision
            == "retain_with_new_evidence"
            and explicit_decision
            == "approve"
        ):
            matched_item_id = (
                proposal_item
                .matched_baseline_item_id
            )

            if matched_item_id is None:
                raise ValueError(
                    "Retained proposal item has no "
                    "matched baseline item ID."
                )

            baseline_item = (
                baseline_by_id.get(
                    matched_item_id
                )
            )

            if baseline_item is None:
                raise ValueError(
                    "Matched baseline SWOT item "
                    "could not be found."
                )

            output_by_item_id[
                matched_item_id
            ] = (
                _retained_item_with_evidence(
                    baseline_item=baseline_item,
                    proposal_item=(
                        proposal_item
                    ),
                )
            )

            approved_candidate_ids.append(
                proposal_item.candidate_id
            )

            continue

        if explicit_decision in {
            "approve",
            "accept_candidate",
        }:
            if (
                explicit_decision
                == "accept_candidate"
            ):
                conflicting_item_id = (
                    proposal_item
                    .matched_baseline_item_id
                )

                if conflicting_item_id is None:
                    raise ValueError(
                        "Accepted conflict item has no "
                        "matched baseline item ID."
                    )

                output_by_item_id.pop(
                    conflicting_item_id,
                    None,
                )

                origin: ApprovedItemOrigin = (
                    "accepted_conflict_candidate"
                )
            else:
                origin = "approved_candidate"

            approved_item = (
                _proposal_item_to_approved(
                    proposal=proposal,
                    item=proposal_item,
                    origin=origin,
                )
            )

            output_by_item_id[
                approved_item.item_id
            ] = approved_item

            approved_candidate_ids.append(
                proposal_item.candidate_id
            )

    actionable_candidate_ids = {
        item.candidate_id
        for item in proposal.items
        if item.decision
        in {
            "add",
            "retain_with_new_evidence",
            "conflict_requires_review",
        }
    }

    approval_complete = not (
        unresolved_candidate_ids
    )

    warnings: list[str] = list(
        proposal.warnings
    )

    if unresolved_candidate_ids:
        warnings.append(
            "One or more actionable SWOT proposal "
            "items do not have an explicit approval "
            "decision."
        )

    strategy_items = [
        item
        for item in output_by_item_id.values()
        if item.should_feed_strategy_agent
    ]

    invalid_strategy_items = [
        item.item_id
        for item in strategy_items
        if (
            item.manual_review_only
            or not item.evidence_references
            or item.claim_strength
            not in {
                "validated",
                "internally_supported",
                "directional",
            }

        )
    ]

    if invalid_strategy_items:
        warnings.append(
            "One or more Strategy-routed SWOT items "
            "failed the approved evidence gate."
        )

    unknown_decision_ids = (
        set(
            decisions_by_candidate
        )
        - actionable_candidate_ids
    )

    if unknown_decision_ids:
        raise ValueError(
            "Approval decisions include unknown "
            "actionable candidates."
        )

    ready_for_strategy = (
        approval_complete
        and not invalid_strategy_items
    )

    return ApprovedSwotUpdate(
        approved_report_id=(
            _approved_report_id(
                proposal=proposal,
                decisions=decisions,
            )
        ),
        business_id=(
            baseline.business_id
        ),
        base_report_id=(
            baseline.report_id
        ),
        source_proposal_id=(
            proposal.proposal_id
        ),
        base_engine_version=(
            baseline.engine_version
        ),
        output_engine_version="8.0",
        source_coverage=(
            proposal.current_sources
        ),
        items=tuple(
            output_by_item_id.values()
        ),
        approved_candidate_ids=tuple(
            approved_candidate_ids
        ),
        rejected_candidate_ids=tuple(
            rejected_candidate_ids
        ),
        unresolved_candidate_ids=tuple(
            unresolved_candidate_ids
        ),
        supporting_signal_candidate_ids=tuple(
            item.candidate_id
            for item
            in proposal.supporting_signals
        ),
        data_gap_candidate_ids=tuple(
            item.candidate_id
            for item in proposal.data_gaps
        ),
        warnings=tuple(
            warnings
        ),
        ready_for_strategy=(
            ready_for_strategy
        ),
        approval_complete=(
            approval_complete
        ),
    )
