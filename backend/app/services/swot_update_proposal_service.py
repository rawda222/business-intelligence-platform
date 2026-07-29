"""
SWOT Update Proposal Service

Compares a normalized existing SWOT baseline with evidence-backed
brand-trend candidates.

The service is deterministic and conservative:

- It does not call an LLM.
- It does not modify the stored SWOT.
- It does not write to MongoDB.
- It does not remove old SWOT items automatically.
- It does not perform semantic matching.
- It never routes draft proposal items to Strategy directly.
"""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5
from uuid import uuid4

from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
    NormalizedSwotItem,
)
from app.services.swot_evidence_candidate_service import (
    SwotEvidenceCandidate,
    SwotQuadrant,
)


ProposalDecision = Literal[
    "add",
    "retain_with_new_evidence",
    "conflict_requires_review",
    "ignore_supporting_signal",
    "ignore_data_gap",
]

ProposalStatus = Literal[
    "draft",
    "approved",
    "rejected",
    "superseded",
]


_PROPOSAL_NAMESPACE = UUID(
    "55555555-5555-5555-5555-555555555555"
)


@dataclass(frozen=True, slots=True)
class SwotUpdateProposalItem:
    """One proposed or ignored SWOT update decision."""

    decision: ProposalDecision

    candidate_id: str

    quadrant: SwotQuadrant | None

    matched_baseline_item_id: str | None

    matched_baseline_quadrant: (
        SwotQuadrant | None
    )

    title: str

    statement: str

    rationale: str

    confidence: float

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

    mapping_rule: str

    eligible_for_strategy_after_approval: bool

    should_feed_strategy_agent: bool

    requires_manual_review: bool


@dataclass(frozen=True, slots=True)
class SwotUpdateProposal:
    """Complete draft update proposal for one SWOT baseline."""

    proposal_id: UUID

    business_id: UUID

    base_report_id: UUID | None

    base_engine_version: str | None

    status: ProposalStatus

    baseline_sources: tuple[
        str,
        ...
    ]

    current_sources: tuple[
        str,
        ...
    ]

    new_sources_since_baseline: tuple[
        str,
        ...
    ]

    items: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    add_items: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    retained_items: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    conflict_items: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    supporting_signals: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    data_gaps: tuple[
        SwotUpdateProposalItem,
        ...
    ]

    unchanged_baseline_item_ids: tuple[
        str,
        ...
    ]

    warnings: tuple[
        str,
        ...
    ]

    requires_human_approval: bool

    proposal_version: str = "1.0"

    proposal_mode: str = "update"


def _normalize_title(
    value: str,
) -> str:
    """
    Normalize one title for conservative exact matching.

    This is lexical normalization only. It does not infer semantic
    similarity between different phrases.
    """

    lowered = value.strip().lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        lowered,
    )

    return " ".join(
        normalized.split()
    )


def _unique_strings(
    values: tuple[
        str,
        ...
    ],
) -> tuple[
    str,
    ...
]:
    """Remove duplicate strings while preserving order."""

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

    return tuple(
        result
    )


def _current_sources(
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
    baseline: NormalizedSwotBaseline,
) -> tuple[
    str,
    ...
]:
    """Combine baseline and observed candidate sources."""

    values: list[str] = list(
        baseline.source_coverage
    )

    for candidate in candidates:
        values.extend(
            candidate.supporting_sources
        )

    return _unique_strings(
        tuple(
            values
        )
    )


def _proposal_id(
    *,
    baseline: NormalizedSwotBaseline,
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
) -> UUID:
    """Build a deterministic proposal identifier."""

    candidate_ids = "|".join(
        candidate.candidate_id
        for candidate in candidates
    )

    identity = (
        f"{baseline.business_id}:"
        f"{baseline.report_id}:"
        f"{candidate_ids}"
    )

    return uuid5(
        _PROPOSAL_NAMESPACE,
        identity,
    )


def _build_title_index(
    baseline: NormalizedSwotBaseline,
) -> dict[
    str,
    tuple[
        NormalizedSwotItem,
        ...
    ],
]:
    """Index baseline items by normalized title."""

    grouped: dict[
        str,
        list[
            NormalizedSwotItem
        ],
    ] = {}

    for item in baseline.items:
        normalized_title = (
            _normalize_title(
                item.title
            )
        )

        if not normalized_title:
            continue

        grouped.setdefault(
            normalized_title,
            [],
        ).append(
            item
        )

    return {
        title: tuple(
            items
        )
        for title, items
        in grouped.items()
    }


def _ignored_item(
    *,
    candidate: SwotEvidenceCandidate,
    decision: ProposalDecision,
) -> SwotUpdateProposalItem:
    """Build an ignored supporting-signal or data-gap item."""

    return SwotUpdateProposalItem(
        decision=decision,
        candidate_id=(
            candidate.candidate_id
        ),
        quadrant=None,
        matched_baseline_item_id=None,
        matched_baseline_quadrant=None,
        title=candidate.title,
        statement=candidate.statement,
        rationale=candidate.rationale,
        confidence=candidate.confidence,
        claim_strength=(
            candidate.claim_strength
        ),
        evidence_references=(
            candidate.evidence_references
        ),
        supporting_sources=(
            candidate.supporting_sources
        ),
        supporting_metrics=(
            candidate.supporting_metrics
        ),
        mapping_rule=(
            candidate.mapping_rule
        ),
        eligible_for_strategy_after_approval=False,
        should_feed_strategy_agent=False,
        requires_manual_review=(
            candidate.requires_manual_review
        ),
    )


def _candidate_decision(
    *,
    candidate: SwotEvidenceCandidate,
    title_index: dict[
        str,
        tuple[
            NormalizedSwotItem,
            ...
        ],
    ],
) -> SwotUpdateProposalItem:
    """Compare one SWOT candidate with baseline titles."""

    normalized_title = _normalize_title(
        candidate.title
    )

    matches = title_index.get(
        normalized_title,
        (),
    )

    same_quadrant_match = next(
        (
            item
            for item in matches
            if (
                item.quadrant
                == candidate.quadrant
            )
        ),
        None,
    )

    conflicting_match = next(
        (
            item
            for item in matches
            if (
                item.quadrant
                != candidate.quadrant
            )
        ),
        None,
    )

    if same_quadrant_match is not None:
        decision: ProposalDecision = (
            "retain_with_new_evidence"
        )

        matched_item = (
            same_quadrant_match
        )

        requires_manual_review = True

        eligible_after_approval = (
            candidate
            .should_feed_strategy_agent
            and (
                matched_item
                .should_feed_strategy_agent
                or candidate.claim_strength
                == "validated"
            )
        )

    elif conflicting_match is not None:
        decision = (
            "conflict_requires_review"
        )

        matched_item = (
            conflicting_match
        )

        requires_manual_review = True

        eligible_after_approval = False

    else:
        decision = "add"

        matched_item = None

        requires_manual_review = True

        eligible_after_approval = (
            candidate
            .should_feed_strategy_agent
        )

    return SwotUpdateProposalItem(
        decision=decision,
        candidate_id=(
            candidate.candidate_id
        ),
        quadrant=candidate.quadrant,
        matched_baseline_item_id=(
            matched_item.item_id
            if matched_item is not None
            else None
        ),
        matched_baseline_quadrant=(
            matched_item.quadrant
            if matched_item is not None
            else None
        ),
        title=candidate.title,
        statement=candidate.statement,
        rationale=candidate.rationale,
        confidence=candidate.confidence,
        claim_strength=(
            candidate.claim_strength
        ),
        evidence_references=(
            candidate.evidence_references
        ),
        supporting_sources=(
            candidate.supporting_sources
        ),
        supporting_metrics=(
            candidate.supporting_metrics
        ),
        mapping_rule=(
            candidate.mapping_rule
        ),
        eligible_for_strategy_after_approval=(
            eligible_after_approval
        ),
        should_feed_strategy_agent=False,
        requires_manual_review=(
            requires_manual_review
        ),
    )


def _build_proposal_item(
    *,
    candidate: SwotEvidenceCandidate,
    title_index: dict[
        str,
        tuple[
            NormalizedSwotItem,
            ...
        ],
    ],
) -> SwotUpdateProposalItem:
    """Route one candidate to the appropriate proposal decision."""

    if candidate.disposition == "data_gap":
        return _ignored_item(
            candidate=candidate,
            decision="ignore_data_gap",
        )

    if (
        candidate.disposition
        == "supporting_signal"
    ):
        return _ignored_item(
            candidate=candidate,
            decision=(
                "ignore_supporting_signal"
            ),
        )

    if candidate.quadrant is None:
        return _ignored_item(
            candidate=candidate,
            decision=(
                "ignore_supporting_signal"
            ),
        )

    return _candidate_decision(
        candidate=candidate,
        title_index=title_index,
    )


def build_swot_update_proposal(
    *,
    baseline: NormalizedSwotBaseline,
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
) -> SwotUpdateProposal:
    """
    Build a draft evidence-based SWOT update proposal.

    The proposal never routes items directly to Strategy. A later
    approval service must create the approved SWOT version first.
    """

    for candidate in candidates:
        if (
            candidate.business_id
            != baseline.business_id
        ):
            raise ValueError(
                "SWOT candidate business_id does "
                "not match the baseline business_id."
            )

    title_index = _build_title_index(
        baseline
    )

    items = tuple(
        _build_proposal_item(
            candidate=candidate,
            title_index=title_index,
        )
        for candidate in candidates
    )

    add_items = tuple(
        item
        for item in items
        if item.decision == "add"
    )

    retained_items = tuple(
        item
        for item in items
        if (
            item.decision
            == "retain_with_new_evidence"
        )
    )

    conflict_items = tuple(
        item
        for item in items
        if (
            item.decision
            == "conflict_requires_review"
        )
    )

    supporting_signals = tuple(
        item
        for item in items
        if (
            item.decision
            == "ignore_supporting_signal"
        )
    )

    data_gaps = tuple(
        item
        for item in items
        if (
            item.decision
            == "ignore_data_gap"
        )
    )

    matched_baseline_ids = {
        item.matched_baseline_item_id
        for item in items
        if (
            item.matched_baseline_item_id
            is not None
        )
    }

    unchanged_baseline_item_ids = tuple(
        item.item_id
        for item in baseline.items
        if (
            item.item_id
            not in matched_baseline_ids
        )
    )

    current_sources = _current_sources(
        candidates,
        baseline,
    )

    baseline_source_set = set(
        baseline.source_coverage
    )

    new_sources_since_baseline = tuple(
        source
        for source in current_sources
        if source not in baseline_source_set
    )

    warnings: list[str] = list(
        baseline.warnings
    )

    if conflict_items:
        warnings.append(
            "One or more evidence candidates "
            "conflict with an existing SWOT quadrant."
        )

    if data_gaps:
        warnings.append(
            "One or more trend signals were blocked "
            "because the available data were insufficient."
        )

    if not candidates:
        warnings.append(
            "No trend evidence candidates were "
            "provided for this proposal."
        )

    return SwotUpdateProposal(
    proposal_id=_proposal_id(
        baseline=baseline,
        candidates=candidates,
    ),

    business_id=(
        baseline.business_id
    ),

    base_report_id=(
        baseline.report_id
    ),

    base_engine_version=(
        baseline.engine_version
    ),

    status="draft",

    baseline_sources=(
        baseline.source_coverage
    ),

    current_sources=(
        current_sources
    ),

    new_sources_since_baseline=(
        new_sources_since_baseline
    ),

    items=items,

    add_items=add_items,

    retained_items=retained_items,

    conflict_items=conflict_items,

    supporting_signals=(
        supporting_signals
    ),

    data_gaps=data_gaps,

    unchanged_baseline_item_ids=(
        unchanged_baseline_item_ids
    ),

    warnings=tuple(
        warnings
    ),

    requires_human_approval=True,

    proposal_mode="update",
)

def build_initial_swot_proposal(
    *,
    business_id,
    candidates,
    source_coverage,
):
    """
    Build the first SWOT proposal when no approved
    SWOT baseline exists.
    """

    title_index = {}

    items = tuple(
        _build_proposal_item(
            candidate=candidate,
            title_index=title_index,
        )
        for candidate in candidates
    )

    return SwotUpdateProposal(
    proposal_id=uuid4(),

    business_id=business_id,

    base_report_id=None,

    base_engine_version=None,

    status="draft",

    proposal_mode="initial",

    baseline_sources=(),

    current_sources=source_coverage,

    new_sources_since_baseline=source_coverage,

    items=items,

    add_items=items,

    retained_items=(),

    conflict_items=(),

    supporting_signals=(),

    data_gaps=(),

    unchanged_baseline_item_ids=(),

    warnings=(
        "Initial SWOT proposal.",
    ),

    requires_human_approval=True,
)