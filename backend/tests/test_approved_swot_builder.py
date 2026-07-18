"""
Approved SWOT Builder Tests
"""

from uuid import UUID

import pytest

from app.services.approved_swot_builder import (
    SwotProposalApprovalDecision,
    build_approved_swot_update,
)
from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
    NormalizedSwotItem,
)
from app.services.swot_evidence_candidate_service import (
    SwotEvidenceCandidate,
)
from app.services.swot_update_proposal_service import (
    build_swot_update_proposal,
)


_BUSINESS_ID = UUID(
    "11111111-aaaa-bbbb-cccc-111111111111"
)

_OTHER_BUSINESS_ID = UUID(
    "22222222-aaaa-bbbb-cccc-222222222222"
)

_REPORT_ID = UUID(
    "33333333-aaaa-bbbb-cccc-333333333333"
)


def _baseline_item(
    *,
    item_id: str = "S_001",
    quadrant: str = "strength",
    title: str = "Strong customer ratings",
    strategy_eligible: bool = True,
) -> NormalizedSwotItem:
    """Build one deterministic normalized baseline item."""

    return NormalizedSwotItem(
        item_id=item_id,
        item_id_was_generated=False,
        quadrant=quadrant,
        title=title,
        reasoning="Legacy evidence-backed reasoning.",
        source_theme="legacy_reviews",
        confidence=0.8,
        strategic_priority=8.0,
        claim_strength=(
            "validated"
            if strategy_eligible
            else "directional_not_validated"
        ),
        source_should_feed_strategy_agent=(
            strategy_eligible
        ),
        should_feed_strategy_agent=(
            strategy_eligible
        ),
        manual_review_only=(
            not strategy_eligible
        ),
        evidence_references=(
            (
                "legacy:review:1",
            )
            if strategy_eligible
            else ()
        ),
        normalization_warnings=(),
    )


def _baseline(
    *items: NormalizedSwotItem,
    business_id: UUID = _BUSINESS_ID,
) -> NormalizedSwotBaseline:
    """Build one deterministic SWOT baseline."""

    return NormalizedSwotBaseline(
        business_id=business_id,
        report_id=_REPORT_ID,
        engine_version="1.0",
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
        ),
        items=tuple(
            items
        ),
        warnings=(),
    )


def _candidate(
    *,
    title: str,
    quadrant: str | None,
    disposition: str = "swot_candidate",
    validated: bool = True,
    business_id: UUID = _BUSINESS_ID,
) -> SwotEvidenceCandidate:
    """Build one deterministic evidence candidate."""

    return SwotEvidenceCandidate(
        candidate_id=(
            "trend:"
            + title.lower().replace(
                " ",
                "_",
            )
        ),
        business_id=business_id,
        disposition=disposition,
        quadrant=quadrant,
        title=title,
        statement=f"Statement for {title}.",
        rationale=f"Rationale for {title}.",
        confidence=(
            0.9
            if validated
            else 0.7
        ),
        claim_strength=(
            "validated"
            if validated
            else "internally_supported"
        ),
        decision=(
            "eligible"
            if validated
            else "manual_review"
        ),
        should_feed_strategy_agent=(
            validated
        ),
        evidence_references=(
            "trend:evidence:1",
        ),
        supporting_sources=(
            "facebook",
            "instagram",
        ),
        supporting_metrics=(
            (
                "first_half_posts",
                2,
            ),
            (
                "second_half_posts",
                8,
            ),
        ),
        mapping_rule="test_mapping_v1",
        requires_manual_review=(
            not validated
        ),
    )


def _proposal(
    *,
    baseline: NormalizedSwotBaseline,
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
):
    """Build one draft proposal for approval tests."""

    return build_swot_update_proposal(
        baseline=baseline,
        candidates=candidates,
    )


def test_approved_add_creates_strategy_eligible_item():
    """A validated approved addition may feed Strategy."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
        validated=True,
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="approve",
            ),
        ),
    )

    assert result.approval_complete

    assert result.ready_for_strategy

    assert len(result.items) == 1

    item = result.items[0]

    assert item.quadrant == "strength"

    assert item.origin == "approved_candidate"

    assert (
        item.should_feed_strategy_agent
    )

    assert not item.manual_review_only

    assert item.evidence_references == (
        "trend:evidence:1",
    )


def test_approved_weak_candidate_stays_out_of_strategy():
    """
    Human approval must not bypass the deterministic quality gate.
    """

    baseline = _baseline()

    candidate = _candidate(
        title="Possible publishing improvement",
        quadrant="strength",
        validated=False,
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="approve",
            ),
        ),
    )

    item = result.items[0]

    assert not (
        item.should_feed_strategy_agent
    )

    assert item.manual_review_only

    assert result.ready_for_strategy


def test_rejected_add_is_not_created():
    """A rejected addition should not enter the approved SWOT."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="reject",
            ),
        ),
    )

    assert result.items == ()

    assert (
        result.rejected_candidate_ids
        == (
            candidate.candidate_id,
        )
    )

    assert result.approval_complete


def test_retained_item_merges_unique_evidence():
    """Approved retained items should merge old and new evidence."""

    baseline_item = _baseline_item(
        title="Increasing Publishing Activity",
    )

    baseline = _baseline(
        baseline_item
    )

    candidate = _candidate(
        title="increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="approve",
            ),
        ),
    )

    assert len(result.items) == 1

    item = result.items[0]

    assert item.item_id == "S_001"

    assert (
        item.origin
        == "retained_with_new_evidence"
    )

    assert item.evidence_references == (
        "legacy:review:1",
        "trend:evidence:1",
    )

    assert (
        item.should_feed_strategy_agent
    )


def test_rejected_retention_preserves_baseline():
    """Rejecting enrichment should preserve the original item."""

    baseline_item = _baseline_item(
        title="Increasing Publishing Activity",
    )

    baseline = _baseline(
        baseline_item
    )

    candidate = _candidate(
        title="increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="reject",
            ),
        ),
    )

    item = result.items[0]

    assert item.origin == "baseline"

    assert item.evidence_references == (
        "legacy:review:1",
    )


def test_keep_baseline_resolves_conflict():
    """Keeping the baseline should resolve a quadrant conflict."""

    baseline_item = _baseline_item(
        title="Stable Customer Ratings",
        quadrant="strength",
    )

    baseline = _baseline(
        baseline_item
    )

    candidate = _candidate(
        title="stable customer ratings",
        quadrant="weakness",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="keep_baseline",
            ),
        ),
    )

    assert result.approval_complete

    assert result.ready_for_strategy

    assert len(result.items) == 1

    assert result.items[0].quadrant == "strength"

    assert result.items[0].origin == "baseline"


def test_accept_candidate_replaces_conflicting_baseline():
    """Accepting the candidate should replace its conflict match."""

    baseline_item = _baseline_item(
        title="Stable Customer Ratings",
        quadrant="strength",
    )

    baseline = _baseline(
        baseline_item
    )

    candidate = _candidate(
        title="stable customer ratings",
        quadrant="weakness",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(
            SwotProposalApprovalDecision(
                candidate_id=(
                    candidate.candidate_id
                ),
                decision="accept_candidate",
            ),
        ),
    )

    assert result.approval_complete

    assert len(result.items) == 1

    item = result.items[0]

    assert item.quadrant == "weakness"

    assert (
        item.origin
        == "accepted_conflict_candidate"
    )

    assert item.base_item_id == "S_001"


def test_missing_decision_keeps_proposal_unresolved():
    """Actionable candidates require an explicit decision."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(),
    )

    assert not result.approval_complete

    assert not result.ready_for_strategy

    assert (
        result.unresolved_candidate_ids
        == (
            candidate.candidate_id,
        )
    )


def test_supporting_signals_and_gaps_never_enter_items():
    """Ignored evidence should remain outside SWOT quadrants."""

    baseline = _baseline()

    support = _candidate(
        title="Observed engagement peak",
        quadrant=None,
        disposition="supporting_signal",
    )

    gap = _candidate(
        title="Insufficient review volume",
        quadrant=None,
        disposition="data_gap",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            support,
            gap,
        ),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(),
    )

    assert result.items == ()

    assert (
        result
        .supporting_signal_candidate_ids
        == (
            support.candidate_id,
        )
    )

    assert (
        result.data_gap_candidate_ids
        == (
            gap.candidate_id,
        )
    )

    assert result.approval_complete


def test_duplicate_approval_decision_is_rejected():
    """One candidate cannot receive two approval decisions."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    duplicate_decision = (
        SwotProposalApprovalDecision(
            candidate_id=(
                candidate.candidate_id
            ),
            decision="approve",
        )
    )

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        build_approved_swot_update(
            baseline=baseline,
            proposal=proposal,
            decisions=(
                duplicate_decision,
                duplicate_decision,
            ),
        )


def test_invalid_decision_for_add_is_rejected():
    """Conflict-only decisions must not be used for additions."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    with pytest.raises(
        ValueError,
        match="not valid",
    ):
        build_approved_swot_update(
            baseline=baseline,
            proposal=proposal,
            decisions=(
                SwotProposalApprovalDecision(
                    candidate_id=(
                        candidate.candidate_id
                    ),
                    decision="keep_baseline",
                ),
            ),
        )


def test_unknown_candidate_decision_is_rejected():
    """Approval decisions must target actionable proposal items."""

    baseline = _baseline()

    proposal = _proposal(
        baseline=baseline,
        candidates=(),
    )

    with pytest.raises(
        ValueError,
        match="unknown",
    ):
        build_approved_swot_update(
            baseline=baseline,
            proposal=proposal,
            decisions=(
                SwotProposalApprovalDecision(
                    candidate_id="unknown",
                    decision="approve",
                ),
            ),
        )


def test_cross_business_proposal_is_rejected():
    """A proposal from another tenant must not be approved."""

    baseline = _baseline()

    other_baseline = _baseline(
        business_id=_OTHER_BUSINESS_ID,
    )

    other_candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
        business_id=_OTHER_BUSINESS_ID,
    )

    other_proposal = _proposal(
        baseline=other_baseline,
        candidates=(
            other_candidate,
        ),
    )

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_approved_swot_update(
            baseline=baseline,
            proposal=other_proposal,
            decisions=(),
        )


def test_approved_report_id_is_deterministic():
    """Identical approval inputs should produce the same ID."""

    baseline = _baseline()

    candidate = _candidate(
        title="Increasing publishing activity",
        quadrant="strength",
    )

    proposal = _proposal(
        baseline=baseline,
        candidates=(
            candidate,
        ),
    )

    decisions = (
        SwotProposalApprovalDecision(
            candidate_id=(
                candidate.candidate_id
            ),
            decision="approve",
        ),
    )

    first = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=decisions,
    )

    second = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=decisions,
    )

    assert (
        first.approved_report_id
        == second.approved_report_id
    )


def test_output_exposes_source_lineage():
    """Approved output should retain source and version lineage."""

    baseline = _baseline()

    proposal = _proposal(
        baseline=baseline,
        candidates=(),
    )

    result = build_approved_swot_update(
        baseline=baseline,
        proposal=proposal,
        decisions=(),
    )

    assert result.business_id == _BUSINESS_ID

    assert result.base_report_id == _REPORT_ID

    assert (
        result.source_proposal_id
        == proposal.proposal_id
    )

    assert result.base_engine_version == "1.0"

    assert result.output_engine_version == "8.0"

    assert result.source_coverage == (
        "business_profile",
        "google_maps_reviews",
    )