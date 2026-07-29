"""
Grounded SWOT Update API

Creates, retrieves, and approves tenant-scoped grounded SWOT
update proposals.

Strategy generation remains a separate workflow and consumes only
a persisted, approved, Strategy-ready SWOT report.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
)
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.business_service import (
    get_business_by_id,
)
from app.services.swot_approval_workflow_service import (
    approve_swot_update_proposal_workflow,
)
from app.services.swot_strategy_persistence_service import (
    get_swot_update_proposal,
)
from app.services.unified_swot_workflow_service import (
    run_unified_swot_workflow,
    run_unified_swot_workflow_from_raw_data,
)


def _build_report_from_accepted(
    generation: Any,
) -> dict[str, list[dict[str, Any]]]:
    """
    Group grounded accepted_items into a SWOT report shape.

    Used for the provisional path, where the generation produced
    validated, evidence-grounded items but the overall result was
    not auto-safe for the approval workflow (e.g. one blocked item).
    Every item is flagged provisional and still requires human review.
    """

    report: dict[str, list[dict[str, Any]]] = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    }

    for item in getattr(generation, "accepted_items", ()):
        quadrant = getattr(item, "quadrant", "")

        if quadrant not in report:
            continue

        report[quadrant].append(
            {
                "title": getattr(item, "title", ""),
                "reasoning": getattr(item, "reasoning", ""),
                "claim_strength": getattr(
                    item,
                    "claim_strength",
                    "directional_not_validated",
                ),
                "evidence_references": list(
                    getattr(item, "evidence_references", ())
                ),
                "provisional": True,
            }
        )

    return report


router = APIRouter(
    prefix=(
        "/businesses/{business_id}/"
        "swot/proposals"
    ),
    tags=[
        "SWOT Updates",
    ],
)


# ============================================================
# Request Schemas
# ============================================================
class SwotProposalCreateRequest(BaseModel):
    """Request for one grounded SWOT update proposal."""

    range_start: datetime

    range_end: datetime

    review_source: str = Field(
        default="google_maps",
        min_length=1,
        max_length=50,
    )

    max_engagement_curves: int = Field(
        default=5,
        ge=0,
        le=20,
    )


class SwotRunRequest(BaseModel):
    """Run the full grounded SWOT workflow from raw data."""

    raw_data: dict

    range_start: datetime

    range_end: datetime

    review_source: str = Field(
        default="google_maps",
        min_length=1,
        max_length=50,
    )

    max_engagement_curves: int = Field(
        default=5,
        ge=0,
        le=20,
    )


class SwotApprovalDecisionRequest(BaseModel):
    """One explicit human decision for one proposal candidate."""

    candidate_id: str = Field(
        min_length=1,
        max_length=500,
    )

    decision: Literal[
        "approve",
        "reject",
        "keep_baseline",
        "accept_candidate",
    ]


class SwotProposalApproveRequest(BaseModel):
    """Explicit human decisions for one draft proposal."""

    decisions: list[
        SwotApprovalDecisionRequest
    ] = Field(
        min_length=1,
    )


# ============================================================
# Ownership Guard
# ============================================================
async def _require_owned_business(
    *,
    db: AsyncSession,
    business_id: UUID,
    current_user: User,
) -> Any:
    """Return a business only when it belongs to the caller."""

    business = await get_business_by_id(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )

    if business is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Business not found",
        )

    return business


# ============================================================
# Response Builders
# ============================================================
def _proposal_response(
    document: Any,
) -> dict[str, Any]:
    """Return the public persisted-proposal representation."""

    return {
        "proposal_id": str(
            document.proposal_id
        ),
        "business_id": str(
            document.business_id
        ),
        "base_report_id": str(
            document.base_report_id
        ),
        "base_engine_version": (
            document.base_engine_version
        ),
        "proposal_version": (
            document.proposal_version
        ),
        "status": document.status,
        "proposal": (
            document.proposal_snapshot
        ),
        "candidates": (
            document.candidate_snapshot
        ),
        "generation_metadata": (
            document.generation_metadata
        ),
        "source_coverage": list(
            document.source_coverage
        ),
        "warnings": list(
            document.warnings
        ),
        "requires_human_approval": (
            document
            .requires_human_approval
        ),
        "approved_report_id": (
            str(
                document.approved_report_id
            )
            if (
                document.approved_report_id
                is not None
            )
            else None
        ),
        "created_at": (
            document.created_at.isoformat()
        ),
        "updated_at": (
            document.updated_at.isoformat()
        ),
    }


def _approval_response(
    result: Any,
) -> dict[str, Any]:
    """Return the public approved-SWOT workflow response."""

    approved_update = (
        result.approved_update
    )
    approved_report = (
        result.approved_report
    )

    persisted_proposal = (
        result.persisted_proposal
    )

    return {
        "business_id": str(
            result.business_id
        ),
        "proposal_id": str(
            result.proposal_id
        ),
        "approved_report_id": str(
            result.approved_report_id
        ),
        "proposal_status": (
            persisted_proposal.status
        ),
        "engine_version": (
            approved_report.engine_version
        ),
        "approval_complete": (
            approved_update
            .approval_complete
        ),
        "ready_for_strategy": (
            approved_update
            .ready_for_strategy
        ),
        "approved_candidate_ids": list(
            approved_update
            .approved_candidate_ids
        ),
        "rejected_candidate_ids": list(
            approved_update
            .rejected_candidate_ids
        ),
        "unresolved_candidate_ids": list(
            approved_update
            .unresolved_candidate_ids
        ),
        "source_coverage": list(
            approved_update
            .source_coverage
        ),
        "swot_report": (
            approved_report.swot_report
        ),
        "validation_results": (
            approved_report
            .validation_results
        ),
        "warnings": list(
            approved_update.warnings
        ),
        "created_at": (
            approved_report
            .created_at
            .isoformat()
        ),
    }


# ============================================================
# POST /businesses/{business_id}/swot/proposals
# ============================================================
@router.post(
    "",
    status_code=(
        status.HTTP_201_CREATED
    ),
    summary=(
        "Create a grounded SWOT update proposal"
    ),
)
async def create_swot_update_proposal(
    business_id: UUID,
    request: SwotProposalCreateRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """
    Generate, validate, and persist one draft SWOT update proposal.

    This endpoint never approves the proposal automatically.
    """

    business = await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        result = await run_unified_swot_workflow(
            business_id=business_id,
            business_name=(
                business.name
            ),
            business_type=(
                business.business_type
            ),
            range_start=(
                request.range_start
            ),
            range_end=(
                request.range_end
            ),
            review_source=(
                request.review_source
            ),
            max_engagement_curves=(
                request
                .max_engagement_curves
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(
                error
            ),
        ) from error

    return _proposal_response(
        result.persisted_proposal
    )


@router.post(
    "/run",
    status_code=(
        status.HTTP_201_CREATED
    ),
    summary=(
        "Run the unified grounded SWOT workflow "
        "from raw data"
    ),
)
async def run_swot_workflow(
    business_id: UUID,
    request: SwotRunRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """
    Build customer voice, themes, trend intelligence, and a grounded
    SWOT proposal directly from raw data.

    The workflow selects initial or update mode automatically and
    never approves the proposal.
    """

    business = await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        result = await (
            run_unified_swot_workflow_from_raw_data(
                business_id=business_id,
                business_name=(
                    business.name
                ),
                business_type=(
                    business.business_type
                ),
                raw_data=request.raw_data,
                range_start=(
                    request.range_start
                ),
                range_end=(
                    request.range_end
                ),
                review_source=(
                    request.review_source
                ),
                max_engagement_curves=(
                    request
                    .max_engagement_curves
                ),
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(
                error
            ),
        ) from error

    if result.persisted_proposal is None:
        return {
            "business_id": str(
                result.business_id
            ),
            "mode": result.mode,
            "coverage_level": (
                result.coverage_level
            ),
            "status": "needs_more_data",
            "proposal_id": None,
            "requires_human_approval": True,
            "swot_report": _build_report_from_accepted(
                result.generation
            ),
            "data_gaps": list(
                result.warnings
            ),
        }

    response = _proposal_response(
        result.persisted_proposal
    )

    response["mode"] = result.mode

    response["coverage_level"] = (
        result.coverage_level
    )

    return response


# ============================================================
# GET /businesses/{business_id}/swot/proposals/{proposal_id}
# ============================================================
@router.get(
    "/{proposal_id}",
    summary=(
        "Get one SWOT update proposal"
    ),
)
async def read_swot_update_proposal(
    business_id: UUID,
    proposal_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return one tenant-scoped persisted SWOT proposal."""

    await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    document = await get_swot_update_proposal(
        business_id=business_id,
        proposal_id=proposal_id,
    )

    if document is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "SWOT update proposal not found"
            ),
        )

    return _proposal_response(
        document
    )


# ============================================================
# POST /businesses/{business_id}/swot/proposals/{proposal_id}/approve
# ============================================================
@router.post(
    "/{proposal_id}/approve",
    status_code=status.HTTP_200_OK,
    summary=(
        "Approve one grounded SWOT update proposal"
    ),
)
async def approve_swot_update_proposal(
    business_id: UUID,
    proposal_id: UUID,
    request: SwotProposalApproveRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """
    Apply explicit human decisions and persist an approved SWOT.

    This endpoint does not run Strategy. Strategy generation remains
    a separate operation that consumes the persisted approved SWOT.
    """

    business = await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    decision_values = tuple(
        decision.model_dump(
            mode="python"
        )
        for decision in request.decisions
    )

    try:
        result = await (
            approve_swot_update_proposal_workflow(
                business_id=business_id,
                proposal_id=proposal_id,
                business_type=(
                    business.business_type
                ),
                decision_values=(
                    decision_values
                ),
            )
        )
    except ValueError as error:
        message = str(
            error
        )

        lowered_message = (
            message.lower()
        )

        if "not found" in lowered_message:
            status_code = (
                status.HTTP_404_NOT_FOUND
            )
        elif "only draft" in lowered_message:
            status_code = (
                status.HTTP_409_CONFLICT
            )
        else:
            status_code = (
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    return _approval_response(
        result
    )