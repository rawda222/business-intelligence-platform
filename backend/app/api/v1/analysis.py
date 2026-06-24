"""
Full Analysis Endpoint
Raw Data → Normalize → Themes → SWOT
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.analysis_pipeline import run_full_analysis
from app.services.business_service import get_business_by_id


router = APIRouter(
    prefix="/businesses/{business_id}/analysis",
    tags=["Analysis"],
)


class AnalysisRequest(BaseModel):
    """Raw business data to run through the full pipeline."""
    raw_data: dict


@router.post(
    "/run",
    status_code=status.HTTP_201_CREATED,
    summary="Run full BI pipeline (Normalize → Themes → SWOT)",
)
async def run_analysis(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the complete Business Intelligence pipeline:
    
    1. **Normalize** the raw scraped data
    2. **Extract themes** from the cleaned reviews
    3. **Generate SWOT** analysis via Gemini
    
    Returns summary with the SWOT report ID and theme previews.
    """

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

    try:
        result = await run_full_analysis(
            business_id=business_id,
            business_type=business.business_type,
            raw_data=request.raw_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {type(e).__name__}: {e}",
        )

    return result