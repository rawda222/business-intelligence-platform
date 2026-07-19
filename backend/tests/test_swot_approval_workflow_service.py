"""
SWOT Approval Workflow Service Tests

Tests snapshot reconstruction, approval decision validation,
tenant isolation, approval completeness, persistence ordering,
and the complete approval workflow without MongoDB.
"""

from dataclasses import asdict
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.approved_swot_builder import (
    SwotProposalApprovalDecision,
)
from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
    NormalizedSwotItem,
)
from app.services.swot_approval_workflow_service import (
    approve_swot_update_proposal_workflow,
    build_approval_decisions,
    restore_normalized_swot_baseline,
    restore_swot_update_proposal,
)
from app.services.swot_strategy_persistence_service import (
    _serialize,
)
from app.services.swot_update_proposal_service import (
    SwotUpdateProposal,
    SwotUpdateProposalItem,
)


_BUSINESS_ID = UUID(
    "11111111-2222-3333-4444-555555555555"
)

_OTHER_BUSINESS_ID = UUID(
    "22222222-3333-4444-5555-666666666666"
)

_BASE_REPORT_ID = UUID(
    "33333333-4444-5555-6666-777777777777"
)

_PROPOSAL_ID = UUID(
    "44444444-5555-6666-7777-888888888888"
)


def _baseline(
    *,
    business_id: UUID = _BUSINESS_ID,
) -> NormalizedSwotBaseline:
    """Build one normalized baseline."""

    baseline_item = NormalizedSwotItem(
        item_id="S_001",
        item_id_was_generated=False,
        quadrant="strength",
        title="Strong product quality",
        reasoning=(
            "Validated customer evidence "
            "supports product quality."
        ),
        source_theme="product_quality",
        confidence=0.9,
        strategic_priority=8.0,
        claim_strength="validated",
        source_should_feed_strategy_agent=True,
        should_feed_strategy_agent=True,
        manual_review_only=False,
        evidence_references=(
            "google_maps:review:g-1",
        ),
        normalization_warnings=(),
    )

    return NormalizedSwotBaseline(
        business_id=business_id,
        report_id=_BASE_REPORT_ID,
        engine_version="7.0",
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
        ),
        items=(
            baseline_item,
        ),
        warnings=(),
    )


def _proposal_item() -> SwotUpdateProposalItem:
    """Build one actionable add proposal item."""

    return SwotUpdateProposalItem(
        decision="add",
        candidate_id="grounded:service-delay",
        quadrant="weakness",
        matched_baseline_item_id=None,
        matched_baseline_quadrant=None,
        title="Recurring service delays",
        statement=(
            "Recurring service delays are "
            "reported by customers."
        ),
        rationale=(
            "Repeated cross-source customer "
            "evidence supports this weakness."
        ),
        confidence=0.85,
        claim_strength="validated",
        evidence_references=(
            "google_maps:review:g-2",
            "facebook:comment:f-1",
        ),
        supporting_sources=(
            "google_maps_reviews",
            "facebook",
        ),
        supporting_metrics=(
            (
                "frequency",
                4,
            ),
        ),
        mapping_rule=(
            "negative_customer_theme_to_weakness"
        ),
        eligible_for_strategy_after_approval=True,
        should_feed_strategy_agent=False,
        requires_manual_review=False,
    )


def _proposal(
    *,
    business_id: UUID = _BUSINESS_ID,
) -> SwotUpdateProposal:
    """Build one deterministic draft proposal."""

    item = _proposal_item()

    return SwotUpdateProposal(
        proposal_id=_PROPOSAL_ID,
        business_id=business_id,
        base_report_id=_BASE_REPORT_ID,
        base_engine_version="7.0",
        status="draft",
        baseline_sources=(
            "business_profile",
            "google_maps_reviews",
        ),
        current_sources=(
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
        new_sources_since_baseline=(
            "facebook",
            "instagram",
        ),
        items=(
            item,
        ),
        add_items=(
            item,
        ),
        retained_items=(),
        conflict_items=(),
        supporting_signals=(),
        data_gaps=(),
        unchanged_baseline_item_ids=(
            "S_001",
        ),
        warnings=(),
        requires_human_approval=True,
        proposal_version="1.0",
    )


def _document(
    *,
    business_id: UUID = _BUSINESS_ID,
    status: str = "draft",
    baseline_business_id: UUID = _BUSINESS_ID,
    proposal_business_id: UUID = _BUSINESS_ID,
):
    """Build one persisted proposal-like document."""

    return SimpleNamespace(
        proposal_id=_PROPOSAL_ID,
        business_id=business_id,
        status=status,
        baseline_snapshot=_serialize(
            _baseline(
                business_id=(
                    baseline_business_id
                )
            )
        ),
        proposal_snapshot=_serialize(
            _proposal(
                business_id=(
                    proposal_business_id
                )
            )
        ),
    )


def test_restores_normalized_baseline_snapshot():
    """Serialized baseline fields should be reconstructed exactly."""

    original = _baseline()

    snapshot = _serialize(
        original
    )

    restored = (
        restore_normalized_swot_baseline(
            snapshot
        )
    )

    assert restored.business_id == (
        _BUSINESS_ID
    )

    assert restored.report_id == (
        _BASE_REPORT_ID
    )

    assert restored.engine_version == "7.0"

    assert restored.source_coverage == (
        "business_profile",
        "google_maps_reviews",
    )

    assert len(restored.items) == 1

    item = restored.items[0]

    assert item.item_id == "S_001"

    assert item.quadrant == "strength"

    assert item.claim_strength == "validated"

    assert item.should_feed_strategy_agent

    assert item.evidence_references == (
        "google_maps:review:g-1",
    )


def test_restores_proposal_and_rebuilds_groups():
    """Proposal item groups should be derived from restored items."""

    original = _proposal()

    snapshot = _serialize(
        original
    )

    restored = restore_swot_update_proposal(
        snapshot
    )

    assert restored.proposal_id == (
        _PROPOSAL_ID
    )

    assert restored.business_id == (
        _BUSINESS_ID
    )

    assert restored.status == "draft"

    assert len(restored.items) == 1

    assert len(restored.add_items) == 1

    assert restored.retained_items == ()

    assert restored.conflict_items == ()

    assert restored.supporting_signals == ()

    assert restored.data_gaps == ()

    item = restored.add_items[0]

    assert item.candidate_id == (
        "grounded:service-delay"
    )

    assert item.quadrant == "weakness"

    assert item.supporting_metrics == (
        (
            "frequency",
            4,
        ),
    )

    assert (
        item
        .eligible_for_strategy_after_approval
    )


def test_builds_typed_approval_decisions():
    """Public decision mappings should become typed decisions."""

    decisions = build_approval_decisions(
        (
            {
                "candidate_id": (
                    "grounded:service-delay"
                ),
                "decision": "approve",
            },
        )
    )

    assert len(decisions) == 1

    assert isinstance(
        decisions[0],
        SwotProposalApprovalDecision,
    )

    assert decisions[0].candidate_id == (
        "grounded:service-delay"
    )

    assert decisions[0].decision == "approve"


def test_invalid_approval_decision_is_rejected():
    """Unknown approval actions must fail before persistence."""

    with pytest.raises(
        ValueError,
        match="Unsupported approval decision",
    ):
        build_approval_decisions(
            (
                {
                    "candidate_id": (
                        "grounded:service-delay"
                    ),
                    "decision": (
                        "automatically_accept"
                    ),
                },
            )
        )


@pytest.mark.asyncio
async def test_approval_workflow_persists_in_safe_order():
    """
    Approved SWOT must be saved before the proposal is marked approved.
    """

    document = _document()

    calls: list[str] = []

    async def load_proposal_fn(
        *,
        business_id,
        proposal_id,
    ):
        calls.append(
            "load"
        )

        assert business_id == (
            _BUSINESS_ID
        )

        assert proposal_id == (
            _PROPOSAL_ID
        )

        return document

    async def save_approved_fn(
        *,
        approved,
        business_type,
    ):
        calls.append(
            "save_approved_swot"
        )

        assert approved.approval_complete

        assert (
            approved
            .unresolved_candidate_ids
            == ()
        )

        assert approved.ready_for_strategy

        assert business_type == "cafe"

        return SimpleNamespace(
            report_id=(
                approved.approved_report_id
            ),
            status="approved",
        )

    async def mark_approved_fn(
        *,
        document,
        decisions,
        approved_report_id,
    ):
        calls.append(
            "mark_proposal_approved"
        )

        assert document.status == "draft"

        assert len(decisions) == 1

        assert decisions[0].decision == (
            "approve"
        )

        document.status = "approved"

        document.approved_report_id = (
            approved_report_id
        )

        return document

    result = await (
        approve_swot_update_proposal_workflow(
            business_id=_BUSINESS_ID,
            proposal_id=_PROPOSAL_ID,
            business_type="cafe",
            decision_values=(
                {
                    "candidate_id": (
                        "grounded:service-delay"
                    ),
                    "decision": "approve",
                },
            ),
            load_proposal_fn=(
                load_proposal_fn
            ),
            save_approved_fn=(
                save_approved_fn
            ),
            mark_approved_fn=(
                mark_approved_fn
            ),
        )
    )

    assert calls == [
        "load",
        "save_approved_swot",
        "mark_proposal_approved",
    ]

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert result.proposal_id == (
        _PROPOSAL_ID
    )

    assert (
        result
        .approved_update
        .approval_complete
    )

    assert (
        result
        .approved_update
        .ready_for_strategy
    )

    assert (
        result
        .approved_update
        .unresolved_candidate_ids
        == ()
    )

    assert (
        result
        .persisted_proposal
        .status
        == "approved"
    )


@pytest.mark.asyncio
async def test_missing_proposal_is_rejected():
    """Unknown tenant-scoped proposals must fail closed."""

    async def load_proposal_fn(
        **kwargs,
    ):
        return None

    with pytest.raises(
        ValueError,
        match="was not found",
    ):
        await (
            approve_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                business_type="cafe",
                decision_values=(),
                load_proposal_fn=(
                    load_proposal_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_non_draft_proposal_is_rejected():
    """An already processed proposal cannot be approved again."""

    async def load_proposal_fn(
        **kwargs,
    ):
        return _document(
            status="approved",
        )

    with pytest.raises(
        ValueError,
        match="Only draft",
    ):
        await (
            approve_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                business_type="cafe",
                decision_values=(),
                load_proposal_fn=(
                    load_proposal_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_cross_business_document_is_rejected():
    """Persisted proposal tenant identity must match the request."""

    async def load_proposal_fn(
        **kwargs,
    ):
        return _document(
            business_id=(
                _OTHER_BUSINESS_ID
            ),
        )

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        await (
            approve_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                business_type="cafe",
                decision_values=(),
                load_proposal_fn=(
                    load_proposal_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_cross_business_baseline_snapshot_is_rejected():
    """Baseline snapshot cannot cross the tenant boundary."""

    async def load_proposal_fn(
        **kwargs,
    ):
        return _document(
            baseline_business_id=(
                _OTHER_BUSINESS_ID
            ),
        )

    with pytest.raises(
        ValueError,
        match="Baseline snapshot business_id",
    ):
        await (
            approve_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                business_type="cafe",
                decision_values=(),
                load_proposal_fn=(
                    load_proposal_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_incomplete_decisions_do_not_persist():
    """Missing actionable decisions must block both writes."""

    document = _document()

    save_called = False

    mark_called = False

    async def load_proposal_fn(
        **kwargs,
    ):
        return document

    async def save_approved_fn(
        **kwargs,
    ):
        nonlocal save_called

        save_called = True

    async def mark_approved_fn(
        **kwargs,
    ):
        nonlocal mark_called

        mark_called = True

    with pytest.raises(
        ValueError,
        match="incomplete",
    ):
        await (
            approve_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                business_type="cafe",
                decision_values=(),
                load_proposal_fn=(
                    load_proposal_fn
                ),
                save_approved_fn=(
                    save_approved_fn
                ),
                mark_approved_fn=(
                    mark_approved_fn
                ),
            )
        )

    assert not save_called

    assert not mark_called