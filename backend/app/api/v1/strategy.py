"""
Grounded Strategy API

Generates and retrieves tenant-scoped Strategy reports.

Strategy generation consumes only the latest persisted SWOT report
that is approved, fully resolved, and explicitly ready for Strategy.
"""

from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
)
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.business_service import (
    get_business_by_id,
)
from app.services.strategy_generation_workflow_service import (
    generate_strategy_workflow,
)
from app.services.swot_strategy_persistence_service import (
    get_latest_strategy_report,
)


router = APIRouter(
    prefix="/businesses/{business_id}/strategy",
    tags=["Strategy"],
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


def _strategy_response(
    document: Any,
) -> dict[str, Any]:
    """Return the public persisted Strategy representation."""

    return {
        "report_id": str(
            document.report_id
        ),
        "business_id": str(
            document.business_id
        ),
        "source_swot_id": str(
            document.source_swot_id
        ),
        "source_proposal_id": (
            str(
                document.source_proposal_id
            )
            if (
                document.source_proposal_id
                is not None
            )
            else None
        ),
        "engine_version": (
            document.engine_version
        ),
        "business_type": (
            document.business_type
        ),
        "strategic_posture": (
            document.strategic_posture
        ),
        "posture_rationale": (
            document.posture_rationale
        ),
        "positioning": (
            document.positioning
        ),
        "audience": list(
            document.audience
        ),
        "value_proposition": (
            document.value_proposition
        ),
        "tone_of_voice": (
            document.tone_of_voice
        ),
        "content_pillars": list(
            document.content_pillars
        ),
        "channels": list(
            document.channels
        ),
        "goals": list(
            document.goals
        ),
        "tows_matrix": (
            document.tows_matrix
        ),
        "priority_action_plan": list(
            document.priority_action_plan
        ),
        "resource_assessment": list(
            document.resource_assessment
        ),
        "campaign_brief_feed": list(
            document.campaign_brief_feed
        ),
        "strategy_quality_report": (
            document.strategy_quality_report
        ),
        "meta": document.meta,
        "created_at": (
            document.created_at.isoformat()
        ),
    }


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Generate Strategy from the latest approved SWOT"
    ),
)
async def generate_business_strategy(
    business_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """
    Generate and persist Strategy from the latest approved SWOT.

    Raw, draft, unresolved, or non-Strategy-ready SWOT reports are
    never accepted as Strategy sources.
    """

    await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        result = await generate_strategy_workflow(
            business_id=business_id,
        )
    except ValueError as error:
        message = str(
            error
        )

        if (
            "no approved" in message.lower()
            or "was found" in message.lower()
        ):
            status_code = (
                status.HTTP_404_NOT_FOUND
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
    except RuntimeError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(
                error
            ),
        ) from error

    return _strategy_response(
        result.persisted_strategy
    )


@router.get(
    "/latest",
    summary="Get the latest persisted Strategy",
)
async def read_latest_business_strategy(
    business_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return the latest tenant-scoped Strategy report."""

    await _require_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    document = await get_latest_strategy_report(
        business_id=business_id,
    )

    if document is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "No Strategy reports found "
                "for this business"
            ),
        )

    return _strategy_response(
        document
    )