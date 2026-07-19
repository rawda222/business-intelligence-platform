"""
Grounded SWOT Update API

Creates and retrieves tenant-scoped draft SWOT update proposals.

The API does not approve proposals and does not run Strategy.
"""

from datetime import datetime
from typing import Any
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
from app.services.swot_strategy_persistence_service import (
    get_swot_update_proposal,
)
from app.services.swot_update_workflow_service import (
    create_swot_update_proposal_workflow,
)


router = APIRouter(
    prefix=(
        "/businesses/{business_id}/"
        "swot/proposals"
    ),
    tags=[
        "SWOT Updates",
    ],
)


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
            document.created_at
            .isoformat()
        ),
        "updated_at": (
            document.updated_at
            .isoformat()
        ),
    }


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

    The endpoint never approves the proposal automatically.
    """

    business = await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        result = await (
            create_swot_update_proposal_workflow(
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