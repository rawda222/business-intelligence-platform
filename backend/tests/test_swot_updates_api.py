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