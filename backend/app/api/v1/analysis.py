"""
Full Analysis Endpoints
=======================
Raw Data -> Normalize -> Themes -> SWOT
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.analysis_pipeline import run_full_analysis
from app.services.preprocessing_service import normalize_data, extract_themes
from app.services.business_service import get_business_by_id


router = APIRouter(
    prefix="/businesses/{business_id}/analysis",
    tags=["Analysis"],
)


# ============================================================
# Request Schema
# ============================================================
class AnalysisRequest(BaseModel):
    """Raw business data to run through the pipeline."""
    raw_data: dict


# ============================================================
# POST /run - Full pipeline (Normalize -> Themes -> SWOT)
# ============================================================
@router.post(
    "/run",
    status_code=status.HTTP_201_CREATED,
    summary="Run full BI pipeline (Normalize -> Themes -> SWOT)",
)
async def run_analysis(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the complete BI pipeline."""
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


# ============================================================
# POST /preview - Preview pipeline (NO Gemini call)
# ============================================================
@router.post(
    "/preview",
    summary="Preview Normalize + Themes (no Gemini call)",
)
async def preview_analysis(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run only Normalize + Theme Extraction (NO Gemini call)."""
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
        normalized = normalize_data(request.raw_data)
        themes = extract_themes(normalized)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {type(e).__name__}: {e}",
        )

    return {
        "business_id": str(business_id),
        "business_name": business.name,
        "stages_completed": ["normalize", "theme_extraction"],
        "stats": {
            "reviews_processed": len(normalized.get("business_reviews", [])),
            "competitors_processed": len(normalized.get("competitors", [])),
            "themes_total": len(themes.get("themes", [])),
        },
        "normalized_data": normalized,
        "themes_data": themes,
    }


# ============================================================
# POST /normalize - Only Normalize stage
# ============================================================
@router.post(
    "/normalize",
    summary="Only Normalize stage (full output)",
)
async def normalize_only(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run only the Normalize stage."""
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
        normalized = normalize_data(request.raw_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Normalize failed: {type(e).__name__}: {e}",
        )

    return normalized


# ============================================================
# POST /themes - Normalize + Theme Extraction
# ============================================================
@router.post(
    "/themes",
    summary="Normalize + Theme Extraction (full themes output)",
)
async def themes_only(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run Normalize + Theme Extraction."""
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
        normalized = normalize_data(request.raw_data)
        themes = extract_themes(normalized)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Theme extraction failed: {type(e).__name__}: {e}",
        )

    return themes