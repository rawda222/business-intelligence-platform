"""
SWOT Update Proposal Service Tests
"""

from uuid import UUID

import pytest

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
    "66666666-6666-6666-6666-666666666666"
)

_OTHER_BUSINESS_ID = UUID(
    "77777777-7777-7777-7777-777777777777"
)

_REPORT_ID = UUID(
    "88888888-8888-8888-8888-888888888888"
)


def _baseline_item(
    *,
    item_id: str,
    quadrant: str,
    title: str,
    strategy_eligible: bool = False,
) -> NormalizedSwotItem:
    """Build one normalized baseline SWOT item."""

    return NormalizedSwotItem(
        item_id=item_id,
        item_id_was_generated=False,
        quadrant=quadrant,
        title=title,
        reasoning=(
            "Existing baseline reasoning."
        ),
        source_theme="legacy_theme",
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
) -> NormalizedSwotBaseline:
    """Build one deterministic legacy baseline."""

    return NormalizedSwotBaseline(
        business_id=_BUSINESS_ID,
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
    business_id: UUID = _BUSINESS_ID,
    validated: bool = False,
    sources: tuple[str, ...] = (
        "facebook",
        "instagram",
    ),
) -> SwotEvidenceCandidate:
    """Build one deterministic trend candidate."""

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
        statement=(
            f"Evidence statement for {title}."
        ),
        rationale=(
            f"Evidence rationale for {title}."
        ),
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
            "insight:test",
        ),
        supporting_sources=sources,
        supporting_metrics=(
            (
                "first_half_posts",
                2,
            ),
            (
                "second_half_posts",
                6,
            ),
        ),
        mapping_rule="test_mapping_v1",
        requires_manual_review=(
            not validated
        ),
    )


def test_new_candidate_becomes_add_proposal():
    """A new candidate should be proposed as an addition."""

    proposal = build_swot_update_proposal(
        baseline=_baseline(),
        candidates=(
            _candidate(
                title=(
                    "Increasing publishing activity"
                ),
                quadrant="strength",
                validated=True,
            ),
        ),
    )

    assert proposal.status == "draft"

    assert proposal.requires_human_approval

    assert len(proposal.add_items) == 1

    item = proposal.add_items[0]

    assert item.decision == "add"

    assert item.quadrant == "strength"

    assert (
        item
        .eligible_for_strategy_after_approval
    )

    assert not (
        item.should_feed_strategy_agent
    )

    assert item.requires_manual_review


def test_same_title_same_quadrant_retains_with_evidence():
    """
    A lexical title match in the same quadrant should retain the
    old item and attach the new evidence through the proposal.
    """

    baseline_item = _baseline_item(
        item_id="S_001",
        quadrant="strength",
        title=(
            "Increasing Publishing Activity"
        ),
        strategy_eligible=True,
    )

    proposal = build_swot_update_proposal(
        baseline=_baseline(
            baseline_item
        ),
        candidates=(
            _candidate(
                title=(
                    "increasing publishing activity"
                ),
                quadrant="strength",
                validated=True,
            ),
        ),
    )

    assert len(
        proposal.retained_items
    ) == 1

    item = proposal.retained_items[0]

    assert (
        item.decision
        == "retain_with_new_evidence"
    )

    assert (
        item.matched_baseline_item_id
        == "S_001"
    )

    assert (
        item.matched_baseline_quadrant
        == "strength"
    )

    assert (
        item
        .eligible_for_strategy_after_approval
    )

    assert (
        proposal
        .unchanged_baseline_item_ids
        == ()
    )


def test_same_title_different_quadrant_creates_conflict():
    """Cross-quadrant matches must require human review."""

    baseline_item = _baseline_item(
        item_id="S_002",
        quadrant="strength",
        title=(
            "Stable customer ratings"
        ),
    )

    proposal = build_swot_update_proposal(
        baseline=_baseline(
            baseline_item
        ),
        candidates=(
            _candidate(
                title=(
                    "Stable Customer Ratings"
                ),
                quadrant="weakness",
                validated=True,
                sources=(
                    "google_maps_reviews",
                ),
            ),
        ),
    )

    assert len(
        proposal.conflict_items
    ) == 1

    item = proposal.conflict_items[0]

    assert (
        item.decision
        == "conflict_requires_review"
    )

    assert (
        item.matched_baseline_item_id
        == "S_002"
    )

    assert (
        item.matched_baseline_quadrant
        == "strength"
    )

    assert not (
        item
        .eligible_for_strategy_after_approval
    )

    assert any(
        "conflict" in warning.lower()
        for warning in proposal.warnings
    )


def test_supporting_signal_is_not_added_to_swot():
    """Supporting evidence should remain outside SWOT quadrants."""

    proposal = build_swot_update_proposal(
        baseline=_baseline(),
        candidates=(
            _candidate(
                title=(
                    "Observed engagement peak"
                ),
                quadrant=None,
                disposition=(
                    "supporting_signal"
                ),
            ),
        ),
    )

    assert proposal.add_items == ()

    assert len(
        proposal.supporting_signals
    ) == 1

    item = (
        proposal.supporting_signals[0]
    )

    assert (
        item.decision
        == "ignore_supporting_signal"
    )

    assert item.quadrant is None

    assert not (
        item
        .eligible_for_strategy_after_approval
    )


def test_data_gap_is_blocked_from_swot():
    """Insufficient data should remain an explicit data gap."""

    proposal = build_swot_update_proposal(
        baseline=_baseline(),
        candidates=(
            _candidate(
                title=(
                    "Insufficient review volume"
                ),
                quadrant=None,
                disposition="data_gap",
                sources=(),
            ),
        ),
    )

    assert proposal.add_items == ()

    assert len(proposal.data_gaps) == 1

    item = proposal.data_gaps[0]

    assert (
        item.decision
        == "ignore_data_gap"
    )

    assert not (
        item.should_feed_strategy_agent
    )

    assert any(
        "insufficient" in warning.lower()
        for warning in proposal.warnings
    )


def test_unmatched_baseline_items_are_preserved():
    """Lack of new evidence must not remove an old SWOT item."""

    baseline_item = _baseline_item(
        item_id="W_001",
        quadrant="weakness",
        title=(
            "Limited review coverage"
        ),
    )

    proposal = build_swot_update_proposal(
        baseline=_baseline(
            baseline_item
        ),
        candidates=(),
    )

    assert (
        proposal
        .unchanged_baseline_item_ids
        == (
            "W_001",
        )
    )

    assert proposal.items == ()

    assert any(
        "No trend evidence candidates"
        in warning
        for warning in proposal.warnings
    )


def test_current_and_new_sources_are_exposed():
    """The proposal should show the source expansion explicitly."""

    proposal = build_swot_update_proposal(
        baseline=_baseline(),
        candidates=(
            _candidate(
                title=(
                    "Increasing publishing activity"
                ),
                quadrant="strength",
                validated=True,
            ),
        ),
    )

    assert proposal.baseline_sources == (
        "business_profile",
        "google_maps_reviews",
    )

    assert proposal.current_sources == (
        "business_profile",
        "google_maps_reviews",
        "facebook",
        "instagram",
    )

    assert (
        proposal.new_sources_since_baseline
        == (
            "facebook",
            "instagram",
        )
    )


def test_cross_business_candidate_is_rejected():
    """Candidates from another tenant must not enter the proposal."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_swot_update_proposal(
            baseline=_baseline(),
            candidates=(
                _candidate(
                    title=(
                        "Increasing publishing activity"
                    ),
                    quadrant="strength",
                    business_id=(
                        _OTHER_BUSINESS_ID
                    ),
                ),
            ),
        )


def test_proposal_id_is_deterministic():
    """Identical inputs should create the same proposal ID."""

    baseline = _baseline()

    candidates = (
        _candidate(
            title=(
                "Increasing publishing activity"
            ),
            quadrant="strength",
            validated=True,
        ),
    )

    first = build_swot_update_proposal(
        baseline=baseline,
        candidates=candidates,
    )

    second = build_swot_update_proposal(
        baseline=baseline,
        candidates=candidates,
    )

    assert (
        first.proposal_id
        == second.proposal_id
    )


def test_different_candidate_set_changes_proposal_id():
    """Proposal identity should include the candidate set."""

    baseline = _baseline()

    first = build_swot_update_proposal(
        baseline=baseline,
        candidates=(
            _candidate(
                title=(
                    "Increasing publishing activity"
                ),
                quadrant="strength",
            ),
        ),
    )

    second = build_swot_update_proposal(
        baseline=baseline,
        candidates=(
            _candidate(
                title=(
                    "Declining publishing activity"
                ),
                quadrant="weakness",
            ),
        ),
    )

    assert (
        first.proposal_id
        != second.proposal_id
    )
