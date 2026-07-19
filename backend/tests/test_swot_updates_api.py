"""
Grounded SWOT Updates API Tests

Tests ownership enforcement, workflow mapping, tenant-scoped
proposal retrieval, and public response serialization without
starting PostgreSQL, MongoDB, or Vertex AI.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

import app.api.v1.swot_updates as api


_BUSINESS_ID = UUID(
    "11111111-2222-3333-4444-555555555555"
)

_USER_ID = UUID(
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
_RANGE_START = datetime(
    2026,
    6,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    7,
    1,
    tzinfo=UTC,
)

_CREATED_AT = datetime(
    2026,
    7,
    19,
    10,
    0,
    tzinfo=UTC,
)

_UPDATED_AT = datetime(
    2026,
    7,
    19,
    10,
    5,
    tzinfo=UTC,
)


def _user():
    """Build one authenticated user-like object."""

    return SimpleNamespace(
        id=_USER_ID,
    )


def _business():
    """Build one owned business-like object."""

    return SimpleNamespace(
        id=_BUSINESS_ID,
        name="Example Cafe",
        business_type="cafe",
    )


def _proposal_document():
    """Build one persisted proposal-like object."""

    return SimpleNamespace(
        proposal_id=_PROPOSAL_ID,
        business_id=_BUSINESS_ID,
        base_report_id=_BASE_REPORT_ID,
        base_engine_version="7.0",
        proposal_version="1.0",
        status="draft",
        proposal_snapshot={
            "proposal_id": str(
                _PROPOSAL_ID
            ),
            "status": "draft",
        },
        candidate_snapshot=[
            {
                "candidate_id": (
                    "grounded:1"
                ),
                "quadrant": "weakness",
            }
        ],
        generation_metadata={
            "provider_used": "vertex_ai",
            "model_used": (
                "gemini-2.5-flash"
            ),
            "fallback_used": False,
        },
        source_coverage=[
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ],
        warnings=[
            "human approval required",
        ],
        requires_human_approval=True,
        approved_report_id=None,
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


@pytest.mark.asyncio
async def test_owner_can_create_grounded_proposal(
    monkeypatch,
):
    """Owned businesses should reach the proposal workflow."""

    document = _proposal_document()

    async def fake_get_business_by_id(
        *,
        db,
        business_id,
        owner_id,
    ):
        assert db == "fake-db"

        assert business_id == (
            _BUSINESS_ID
        )

        assert owner_id == _USER_ID

        return _business()

    async def fake_workflow(
        **kwargs,
    ):
        assert kwargs[
            "business_id"
        ] == _BUSINESS_ID

        assert kwargs[
            "business_name"
        ] == "Example Cafe"

        assert kwargs[
            "business_type"
        ] == "cafe"

        assert kwargs[
            "range_start"
        ] == _RANGE_START

        assert kwargs[
            "range_end"
        ] == _RANGE_END

        assert kwargs[
            "review_source"
        ] == "google_maps"

        assert kwargs[
            "max_engagement_curves"
        ] == 5

        return SimpleNamespace(
            persisted_proposal=document,
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        "create_swot_update_proposal_workflow",
        fake_workflow,
    )

    request = api.SwotProposalCreateRequest(
        range_start=_RANGE_START,
        range_end=_RANGE_END,
    )

    response = await (
        api.create_swot_update_proposal(
            business_id=_BUSINESS_ID,
            request=request,
            current_user=_user(),
            db="fake-db",
        )
    )

    assert response[
        "proposal_id"
    ] == str(
        _PROPOSAL_ID
    )

    assert response[
        "business_id"
    ] == str(
        _BUSINESS_ID
    )

    assert response["status"] == "draft"

    assert response[
        "requires_human_approval"
    ]

    assert response[
        "approved_report_id"
    ] is None

    assert response[
        "generation_metadata"
    ]["provider_used"] == "vertex_ai"


@pytest.mark.asyncio
async def test_non_owner_cannot_create_proposal(
    monkeypatch,
):
    """Missing or non-owned businesses should return 404."""

    workflow_called = False

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return None

    async def fake_workflow(
        **kwargs,
    ):
        nonlocal workflow_called

        workflow_called = True

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        "create_swot_update_proposal_workflow",
        fake_workflow,
    )

    request = api.SwotProposalCreateRequest(
        range_start=_RANGE_START,
        range_end=_RANGE_END,
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await api.create_swot_update_proposal(
            business_id=_BUSINESS_ID,
            request=request,
            current_user=_user(),
            db="fake-db",
        )

    assert (
        error_info.value.status_code
        == 404
    )

    assert not workflow_called


@pytest.mark.asyncio
async def test_workflow_validation_error_becomes_422(
    monkeypatch,
):
    """Domain validation failures should become HTTP 422."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_workflow(
        **kwargs,
    ):
        raise ValueError(
            "A stored SWOT baseline is required."
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        "create_swot_update_proposal_workflow",
        fake_workflow,
    )

    request = api.SwotProposalCreateRequest(
        range_start=_RANGE_START,
        range_end=_RANGE_END,
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await api.create_swot_update_proposal(
            business_id=_BUSINESS_ID,
            request=request,
            current_user=_user(),
            db="fake-db",
        )

    assert (
        error_info.value.status_code
        == 422
    )

    assert (
        "baseline"
        in error_info.value.detail
    )


@pytest.mark.asyncio
async def test_owner_can_read_tenant_scoped_proposal(
    monkeypatch,
):
    """Proposal reads should preserve business and proposal scope."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_get_proposal(
        *,
        business_id,
        proposal_id,
    ):
        assert business_id == (
            _BUSINESS_ID
        )

        assert proposal_id == (
            _PROPOSAL_ID
        )

        return _proposal_document()

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        "get_swot_update_proposal",
        fake_get_proposal,
    )

    response = await (
        api.read_swot_update_proposal(
            business_id=_BUSINESS_ID,
            proposal_id=_PROPOSAL_ID,
            current_user=_user(),
            db="fake-db",
        )
    )

    assert response[
        "proposal_id"
    ] == str(
        _PROPOSAL_ID
    )

    assert response[
        "business_id"
    ] == str(
        _BUSINESS_ID
    )

    assert response[
        "base_report_id"
    ] == str(
        _BASE_REPORT_ID
    )

    assert response[
        "created_at"
    ] == _CREATED_AT.isoformat()

    assert response[
        "updated_at"
    ] == _UPDATED_AT.isoformat()


@pytest.mark.asyncio
async def test_missing_proposal_returns_404(
    monkeypatch,
):
    """An unknown tenant-scoped proposal should return 404."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_get_proposal(
        **kwargs,
    ):
        return None

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        "get_swot_update_proposal",
        fake_get_proposal,
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await api.read_swot_update_proposal(
            business_id=_BUSINESS_ID,
            proposal_id=_PROPOSAL_ID,
            current_user=_user(),
            db="fake-db",
        )

    assert (
        error_info.value.status_code
        == 404
    )

    assert (
        error_info.value.detail
        == "SWOT update proposal not found"
    )
@pytest.mark.asyncio
async def test_owner_can_approve_proposal(
    monkeypatch,
):
    """An owner can approve a draft SWOT proposal."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_approval_workflow(
        **kwargs,
    ):
        assert kwargs[
            "business_id"
        ] == _BUSINESS_ID

        assert kwargs[
            "proposal_id"
        ] == _PROPOSAL_ID

        assert kwargs[
            "business_type"
        ] == "cafe"

        assert kwargs[
            "decision_values"
        ] == (
            {
                "candidate_id": (
                    "grounded:service-delay"
                ),
                "decision": "approve",
            },
        )

        approved_update = SimpleNamespace(
            approval_complete=True,
            ready_for_strategy=True,
            approved_candidate_ids=(
                "grounded:service-delay",
            ),
            rejected_candidate_ids=(),
            unresolved_candidate_ids=(),
            source_coverage=(
                "business_profile",
                "google_maps_reviews",
                "facebook",
                "instagram",
            ),
            warnings=(),
        )

        approved_report = SimpleNamespace(
            report_id=(
                _APPROVED_REPORT_ID
            ),
            engine_version="8.0",
            swot_report={
                "strengths": [],
                "weaknesses": [
                    {
                        "item_id": "W_001",
                        "title": (
                            "Recurring service delays"
                        ),
                    }
                ],
                "opportunities": [],
                "threats": [],
            },
            validation_results={
                "overall_status": "PASS",
            },
            created_at=_UPDATED_AT,
        )

        persisted_proposal = (
            SimpleNamespace(
                status="approved",
            )
        )

        return SimpleNamespace(
            business_id=_BUSINESS_ID,
            proposal_id=_PROPOSAL_ID,
            approved_report_id=(
                _APPROVED_REPORT_ID
            ),
            approved_update=(
                approved_update
            ),
            approved_report=(
                approved_report
            ),
            persisted_proposal=(
                persisted_proposal
            ),
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        (
            "approve_swot_update_"
            "proposal_workflow"
        ),
        fake_approval_workflow,
    )

    request = (
        api.SwotProposalApproveRequest(
            decisions=[
                (
                    api
                    .SwotApprovalDecisionRequest(
                        candidate_id=(
                            "grounded:"
                            "service-delay"
                        ),
                        decision="approve",
                    )
                )
            ]
        )
    )

    response = await (
        api.approve_swot_update_proposal(
            business_id=_BUSINESS_ID,
            proposal_id=_PROPOSAL_ID,
            request=request,
            current_user=_user(),
            db="fake-db",
        )
    )

    assert response[
        "business_id"
    ] == str(
        _BUSINESS_ID
    )

    assert response[
        "proposal_id"
    ] == str(
        _PROPOSAL_ID
    )

    assert response[
        "approved_report_id"
    ] == str(
        _APPROVED_REPORT_ID
    )

    assert (
        response["proposal_status"]
        == "approved"
    )

    assert response[
        "approval_complete"
    ]

    assert response[
        "ready_for_strategy"
    ]

    assert response[
        "approved_candidate_ids"
    ] == [
        "grounded:service-delay",
    ]

    assert response[
        "unresolved_candidate_ids"
    ] == []

    assert (
        response[
            "validation_results"
        ]["overall_status"]
        == "PASS"
    )


@pytest.mark.asyncio
async def test_non_owner_cannot_approve_proposal(
    monkeypatch,
):
    """A non-owner cannot reach the approval workflow."""

    workflow_called = False

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return None

    async def fake_approval_workflow(
        **kwargs,
    ):
        nonlocal workflow_called

        workflow_called = True

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        (
            "approve_swot_update_"
            "proposal_workflow"
        ),
        fake_approval_workflow,
    )

    request = (
        api.SwotProposalApproveRequest(
            decisions=[
                (
                    api
                    .SwotApprovalDecisionRequest(
                        candidate_id=(
                            "grounded:"
                            "service-delay"
                        ),
                        decision="approve",
                    )
                )
            ]
        )
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await (
            api.approve_swot_update_proposal(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                request=request,
                current_user=_user(),
                db="fake-db",
            )
        )

    assert (
        error_info.value.status_code
        == 404
    )

    assert (
        error_info.value.detail
        == "Business not found"
    )

    assert not workflow_called


@pytest.mark.asyncio
async def test_missing_approval_proposal_returns_404(
    monkeypatch,
):
    """A missing proposal maps to HTTP 404."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_approval_workflow(
        **kwargs,
    ):
        raise ValueError(
            "SWOT update proposal was not found."
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        (
            "approve_swot_update_"
            "proposal_workflow"
        ),
        fake_approval_workflow,
    )

    request = (
        api.SwotProposalApproveRequest(
            decisions=[
                (
                    api
                    .SwotApprovalDecisionRequest(
                        candidate_id=(
                            "grounded:"
                            "service-delay"
                        ),
                        decision="approve",
                    )
                )
            ]
        )
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await (
            api.approve_swot_update_proposal(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                request=request,
                current_user=_user(),
                db="fake-db",
            )
        )

    assert (
        error_info.value.status_code
        == 404
    )

    assert (
        error_info.value.detail
        == (
            "SWOT update proposal "
            "was not found."
        )
    )


@pytest.mark.asyncio
async def test_non_draft_approval_returns_409(
    monkeypatch,
):
    """Repeated approval maps to HTTP 409 Conflict."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_approval_workflow(
        **kwargs,
    ):
        raise ValueError(
            "Only draft SWOT update proposals "
            "may be approved."
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        (
            "approve_swot_update_"
            "proposal_workflow"
        ),
        fake_approval_workflow,
    )

    request = (
        api.SwotProposalApproveRequest(
            decisions=[
                (
                    api
                    .SwotApprovalDecisionRequest(
                        candidate_id=(
                            "grounded:"
                            "service-delay"
                        ),
                        decision="approve",
                    )
                )
            ]
        )
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await (
            api.approve_swot_update_proposal(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                request=request,
                current_user=_user(),
                db="fake-db",
            )
        )

    assert (
        error_info.value.status_code
        == 409
    )

    assert (
        "Only draft"
        in error_info.value.detail
    )


@pytest.mark.asyncio
async def test_incomplete_approval_returns_422(
    monkeypatch,
):
    """Incomplete decisions map to HTTP 422."""

    async def fake_get_business_by_id(
        **kwargs,
    ):
        return _business()

    async def fake_approval_workflow(
        **kwargs,
    ):
        raise ValueError(
            "Approval decisions are incomplete."
        )

    monkeypatch.setattr(
        api,
        "get_business_by_id",
        fake_get_business_by_id,
    )

    monkeypatch.setattr(
        api,
        (
            "approve_swot_update_"
            "proposal_workflow"
        ),
        fake_approval_workflow,
    )

    request = (
        api.SwotProposalApproveRequest(
            decisions=[
                (
                    api
                    .SwotApprovalDecisionRequest(
                        candidate_id=(
                            "grounded:"
                            "service-delay"
                        ),
                        decision="approve",
                    )
                )
            ]
        )
    )

    with pytest.raises(
        HTTPException,
    ) as error_info:
        await (
            api.approve_swot_update_proposal(
                business_id=(
                    _BUSINESS_ID
                ),
                proposal_id=(
                    _PROPOSAL_ID
                ),
                request=request,
                current_user=_user(),
                db="fake-db",
            )
        )

    assert (
        error_info.value.status_code
        == 422
    )

    assert (
        error_info.value.detail
        == (
            "Approval decisions are "
            "incomplete."
        )
    )