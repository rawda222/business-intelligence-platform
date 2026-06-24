"""
SWOT Endpoints
Generate and retrieve SWOT reports.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.ai_service import (
    generate_swot_report,
    get_latest_swot_report,
    list_swot_reports,
)
from app.services.business_service import get_business_by_id


router = APIRouter(prefix="/businesses/{business_id}/swot", tags=["SWOT"])


# ============================================================
# Request Schema
# ============================================================
class SWOTGenerateRequest(BaseModel):
    """Request to generate a SWOT report."""
    themes_data: dict[str, Any]


# ============================================================
# POST /businesses/{id}/swot/generate
# ============================================================
@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new SWOT report",
)
async def generate_swot(
    business_id: UUID,
    request: SWOTGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new SWOT analysis for the business.
    Uses Gemini to analyze the provided themes.
    """
    # Verify business ownership
    business = await get_business_by_id(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    
    # Generate SWOT
    report = await generate_swot_report(
        business_id=business_id,
        business_type=business.business_type,
        themes_data=request.themes_data,
    )
    
    return {
        "id": str(report.id),
        "business_id": str(report.business_id),
        "engine_version": report.engine_version,
        "business_type": report.business_type,
        "swot_report": report.swot_report,
        "strategic_summary": report.strategic_summary,
        "meta": report.meta,
        "created_at": report.created_at.isoformat(),
    }


# ============================================================
# GET /businesses/{id}/swot/latest
# ============================================================
@router.get(
    "/latest",
    summary="Get latest SWOT report",
)
async def get_latest_swot(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent SWOT report."""
    # Verify ownership
    business = await get_business_by_id(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    
    report = await get_latest_swot_report(business_id=business_id)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SWOT reports found for this business",
        )
    
    return {
        "id": str(report.id),
        "business_id": str(report.business_id),
        "engine_version": report.engine_version,
        "business_type": report.business_type,
        "swot_report": report.swot_report,
        "strategic_summary": report.strategic_summary,
        "watchouts": report.watchouts,
        "meta": report.meta,
        "created_at": report.created_at.isoformat(),
    }


# ============================================================
# GET /businesses/{id}/swot/history
# ============================================================
@router.get(
    "/history",
    summary="List SWOT report history",
)
async def list_swot_history(
    business_id: UUID,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent SWOT reports for a business."""
    business = await get_business_by_id(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )
    
    reports = await list_swot_reports(business_id=business_id, limit=limit)
    
    return {
        "items": [
            {
                "id": str(r.id),
                "engine_version": r.engine_version,
                "business_type": r.business_type,
                "created_at": r.created_at.isoformat(),
                "meta": r.meta,
            }
            for r in reports
        ],
        "total": len(reports),
    }