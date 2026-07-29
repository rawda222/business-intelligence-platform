"""
Full Analysis Endpoints
=======================
# Adapt -> Normalize -> Semantic Themes
# Grounded SWOT continues through /swot/proposals
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.preprocessing.scraper_adapter import (
    adapt_scraper_data,
)
from app.services.analysis_pipeline import (
    run_full_analysis,
)
from app.services.business_service import (
    get_business_by_id,
)
from app.services.preprocessing_service import (
    extract_themes,
    normalize_data,
)


router = APIRouter(
    prefix="/businesses/{business_id}/analysis",
    tags=["Analysis"],
)


# ============================================================
# Request Schema
# ============================================================


class AnalysisRequest(BaseModel):
    """Raw business or scraper data."""

    raw_data: dict


# ============================================================
# Shared Helpers
# ============================================================


async def _get_owned_business(
    *,
    db: AsyncSession,
    business_id: UUID,
    current_user: User,
):
    """Return a Business owned by the authenticated user."""

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

    return business


def _adapt_and_normalize(
    raw_data: dict,
) -> dict:
    """Convert scraper output into normalized pipeline data."""

    adapted_raw = adapt_scraper_data(
        raw_data
    )

    normalized = normalize_data(
        adapted_raw
    )

    return normalized


# ============================================================
# POST /run
# Full Pipeline:
# Adapt -> Normalize -> Semantic Themes -> SWOT
# ============================================================


@router.post(
    "/run",
    status_code=status.HTTP_201_CREATED,
summary=(
    "Run preprocessing "
    "(Adapt -> Normalize -> Semantic Themes)"
),
)
async def run_analysis(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run the complete Business Intelligence pipeline."""

    business = await _get_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        adapted_raw = adapt_scraper_data(
            request.raw_data
        )

        result = await run_full_analysis(
            business_id=business_id,
            business_type=business.business_type,
            raw_data=adapted_raw,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Pipeline input could not be processed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Pipeline failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    return result


# ============================================================
# POST /preview
# Adapt -> Normalize -> Semantic Themes
# ============================================================


@router.post(
    "/preview",
    summary=(
        "Preview Adapt + Normalize + "
        "AI Semantic Theme Extraction"
    ),
)
async def preview_analysis(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run adaptation, normalization, and semantic themes."""

    business = await _get_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        normalized = _adapt_and_normalize(
            request.raw_data
        )

        themes = extract_themes(
            normalized
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Preview failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Preview failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    return {
        "business_id": str(business_id),
        "business_name": business.name,
        "stages_completed": [
            "adapt",
            "normalize",
            "semantic_theme_extraction",
        ],
        "stats": {
            "reviews_processed": len(
                normalized.get(
                    "business_reviews",
                    [],
                )
            ),
            "competitors_processed": len(
                normalized.get(
                    "competitors",
                    [],
                )
            ),
            "themes_total": len(
                themes.get(
                    "themes",
                    [],
                )
            ),
            "positive_signals": len(
                themes.get(
                    "positive_signals",
                    [],
                )
            ),
            "negative_signals": len(
                themes.get(
                    "negative_signals",
                    [],
                )
            ),
            "opportunity_signals": len(
                themes.get(
                    "opportunity_signals",
                    [],
                )
            ),
            "threat_signals": len(
                themes.get(
                    "threat_signals",
                    [],
                )
            ),
        },
        "normalized_data": normalized,
        "themes_data": themes,
    }


# ============================================================
# POST /normalize
# Adapt -> Normalize
# ============================================================


@router.post(
    "/normalize",
    summary="Adapt and normalize raw business data",
)
async def normalize_only(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run scraper adaptation and normalization only."""

    await _get_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        normalized = _adapt_and_normalize(
            request.raw_data
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Normalization input could not be processed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Normalize failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    return normalized


# ============================================================
# POST /themes
# Adapt -> Normalize -> AI Semantic Theme Extraction
# ============================================================


@router.post(
    "/themes",
    summary=(
        "Adapt + Normalize + "
        "AI Semantic Theme Extraction"
    ),
)
async def themes_only(
    business_id: UUID,
    request: AnalysisRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run adaptation, normalization, and semantic themes."""

    await _get_owned_business(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        normalized = _adapt_and_normalize(
            request.raw_data
        )

        themes = extract_themes(
            normalized
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Theme extraction failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Theme extraction failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    return themes