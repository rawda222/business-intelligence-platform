"""
Strategy Generation Workflow Service Tests

Tests approved SWOT restoration, approval gates, Strategy execution,
and persistence lineage without MongoDB or Vertex AI.
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.strategy_generation_workflow_service import (
    generate_strategy_workflow,
    restore_approved_swot_update,
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

_APPROVED_REPORT_ID = UUID(
    "55555555-6666-7777-8888-999999999999"
)

_STRATEGY_REPORT_ID = UUID(
    "66666666-7777-8888-9999-000000000000"
)


def _approved_item():
    """Build one persisted approved SWOT item."""

    return {
        "item_id": "W_001",
        "quadrant": "weakness",
        "title": "Recurring service delays",
        "reasoning": (
            "Approved evidence identifies "
            "recurring service delays."
        ),
        "source_theme": "service_speed",
        "confidence": 0.85,
        "strategic_priority": 8.0,
        "claim_strength": "validated",
        "evidence_references": [
            "google_maps:review:g-1",
        ],
        "supporting_sources": [
            "google_maps_reviews",
        ],
        "supporting_metrics": [
            [
                "frequency",
                4,
            ],
        ],
        "should_feed_strategy_agent": True,
        "manual_review_only": False,
        "origin": "approved_candidate",
        "base_item_id": None,
        "source_candidate_id": (
            "grounded:service-delay"
        ),
    }


def _approved_document(
    *,
    business_id: UUID = _BUSINESS_ID,
    status: str = "approved",
    approval_complete: bool = True,
    ready_for_strategy: bool = True,
    unresolved_candidate_ids=(),
):
    """Build one approved SWOT document-like object."""

    return SimpleNamespace(
        report_id=_APPROVED_REPORT_ID,
        business_id=business_id,
        base_report_id=_BASE_REPORT_ID,
        source_proposal_id=_PROPOSAL_ID,
        engine_version="8.0",
        business_type="cafe",
        status=status,
        approval_complete=(
            approval_complete
        ),
        ready_for_strategy=(
            ready_for_strategy
        ),
        approved_candidate_ids=[
            "grounded:service-delay",
        ],
        rejected_candidate_ids=[],
        unresolved_candidate_ids=list(
            unresolved_candidate_ids
        ),
        source_coverage=[
            "business_profile",
            "google_maps_reviews",
        ],
        swot_report={
            "strengths": [],
            "weaknesses": [
                _approved_item(),
            ],
            "opportunities": [],
            "threats": [],
        },
        meta={
            "base_engine_version": "7.0",
            "version": "1.0",
            "warnings": [],
        },
    )


def test_restores_approved_swot_document():
    """Persisted approved items should restore exactly."""

    approved = restore_approved_swot_update(
        _approved_document(),
        expected_business_id=_BUSINESS_ID,
    )

    assert approved.business_id == (
        _BUSINESS_ID
    )

    assert approved.approved_report_id == (
        _APPROVED_REPORT_ID
    )

    assert approved.source_proposal_id == (
        _PROPOSAL_ID
    )

    assert approved.approval_complete

    assert approved.ready_for_strategy

    assert len(approved.items) == 1

    item = approved.items[0]

    assert item.item_id == "W_001"

    assert item.quadrant == "weakness"

    assert (
        item.should_feed_strategy_agent
    )

    assert item.supporting_metrics == (
        (
            "frequency",
            4,
        ),
    )


@pytest.mark.asyncio
async def test_generates_and_persists_strategy():
    """Strategy should run and persist with approved lineage."""

    approved_document = (
        _approved_document()
    )

    strategy_output = {
        "business_type": "cafe",
        "engine_version": "2.0",
        "strategic_posture": "balanced",
        "positioning": {
            "statement": (
                "A service-focused cafe."
            ),
        },
    }

    calls: list[str] = []

    async def load_approved_fn(
        *,
        business_id,
    ):
        calls.append(
            "load_approved"
        )

        assert business_id == (
            _BUSINESS_ID
        )

        return approved_document

    def build_chain_fn(
        *,
        preferred,
        model,
    ):
        calls.append(
            "build_chain"
        )

        assert model == (
            "gemini-2.5-flash"
        )

        return [
            SimpleNamespace(
                provider_name="vertex_ai"
            )
        ]

    def run_strategy_fn(
        **kwargs,
    ):
        calls.append(
            "run_strategy"
        )

        assert (
            kwargs["approved"]
            .approved_report_id
            == _APPROVED_REPORT_ID
        )

        assert (
            kwargs["business_type"]
            == "cafe"
        )

        assert kwargs[
            "expected_business_id"
        ] == _BUSINESS_ID

        assert kwargs["llm_chain"]

        return SimpleNamespace(
            business_id=_BUSINESS_ID,
            approved_report_id=(
                _APPROVED_REPORT_ID
            ),
            strategy_input={},
            strategy_output=(
                strategy_output
            ),
            eligible_item_count=1,
            excluded_item_count=0,
            strategy_executed=True,
            source_coverage=(),
            warnings=(),
        )

    async def save_strategy_fn(
        **kwargs,
    ):
        calls.append(
            "save_strategy"
        )

        assert kwargs[
            "business_id"
        ] == _BUSINESS_ID

        assert (
            kwargs["approved_swot"]
            is approved_document
        )

        assert (
            kwargs["strategy_output"]
            is strategy_output
        )

        return SimpleNamespace(
            report_id=_STRATEGY_REPORT_ID,
            business_id=_BUSINESS_ID,
            source_swot_id=(
                _APPROVED_REPORT_ID
            ),
        )

    result = await generate_strategy_workflow(
        business_id=_BUSINESS_ID,
        load_approved_fn=(
            load_approved_fn
        ),
        build_chain_fn=(
            build_chain_fn
        ),
        run_strategy_fn=(
            run_strategy_fn
        ),
        save_strategy_fn=(
            save_strategy_fn
        ),
    )

    assert calls == [
        "load_approved",
        "build_chain",
        "run_strategy",
        "save_strategy",
    ]

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert (
        result.source_swot_report_id
        == _APPROVED_REPORT_ID
    )

    assert (
        result.persisted_strategy
        .report_id
        == _STRATEGY_REPORT_ID
    )


@pytest.mark.asyncio
async def test_missing_approved_swot_is_rejected():
    """Strategy cannot run without an approved SWOT."""

    async def load_approved_fn(
        **kwargs,
    ):
        return None

    with pytest.raises(
        ValueError,
        match="No approved",
    ):
        await generate_strategy_workflow(
            business_id=_BUSINESS_ID,
            load_approved_fn=(
                load_approved_fn
            ),
        )


@pytest.mark.parametrize(
    (
        "status",
        "approval_complete",
        "ready_for_strategy",
        "unresolved",
    ),
    [
        (
            "generated",
            True,
            True,
            (),
        ),
        (
            "approved",
            False,
            True,
            (),
        ),
        (
            "approved",
            True,
            False,
            (),
        ),
        (
            "approved",
            True,
            True,
            (
                "grounded:pending",
            ),
        ),
    ],
)
def test_invalid_approval_gate_is_rejected(
    status,
    approval_complete,
    ready_for_strategy,
    unresolved,
):
    """Every Strategy source must pass all approval gates."""

    with pytest.raises(
        ValueError,
    ):
        restore_approved_swot_update(
            _approved_document(
                status=status,
                approval_complete=(
                    approval_complete
                ),
                ready_for_strategy=(
                    ready_for_strategy
                ),
                unresolved_candidate_ids=(
                    unresolved
                ),
            ),
            expected_business_id=(
                _BUSINESS_ID
            ),
        )


def test_cross_business_approved_swot_is_rejected():
    """Approved SWOT cannot cross tenant boundaries."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        restore_approved_swot_update(
            _approved_document(
                business_id=(
                    _OTHER_BUSINESS_ID
                )
            ),
            expected_business_id=(
                _BUSINESS_ID
            ),
        )


@pytest.mark.asyncio
async def test_empty_llm_chain_is_rejected():
    """Strategy generation requires an available LLM client."""

    async def load_approved_fn(
        **kwargs,
    ):
        return _approved_document()

    def build_chain_fn(
        **kwargs,
    ):
        return []

    with pytest.raises(
        RuntimeError,
        match="No Strategy LLM",
    ):
        await generate_strategy_workflow(
            business_id=_BUSINESS_ID,
            load_approved_fn=(
                load_approved_fn
            ),
            build_chain_fn=(
                build_chain_fn
            ),
        )