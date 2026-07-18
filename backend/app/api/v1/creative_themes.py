"""
Automatic Creative Theme Endpoints

Provides two authenticated business-scoped creative-theme views:

- Full automatic resolution for internal audit and diagnostics.
- Compact image-generation handoff for downstream image services.

Every request verifies business ownership before loading social
accounts or resolving creative context.
"""

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
from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
)
from app.creative_context.exceptions import (
    CreativeContextError,
)
from app.creative_context.image_handoff_mapper import (
    map_image_generation_handoff,
)
from app.creative_context.response_mapper import (
    map_automatic_creative_theme_response,
)
from app.creative_context.schemas import (
    AutomaticCreativeThemeResponse,
    ImageGenerationHandoff,
)
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.business_service import (
    get_business_by_id,
)
from app.services.social_account_service import (
    list_active_social_accounts_for_business,
)


router = APIRouter(
    prefix=(
        "/businesses/{business_id}"
        "/creative-themes"
    ),
    tags=["Creative Themes"],
)


async def _resolve_full_response(
    *,
    business_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> AutomaticCreativeThemeResponse:
    """
    Resolve the authenticated business into the full public contract.

    A 404 response is used for both missing and cross-tenant
    businesses so that tenant existence is not disclosed.
    """

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

    social_accounts = await (
        list_active_social_accounts_for_business(
            db=db,
            business_id=business.id,
        )
    )

    try:
        internal_result = (
            resolve_automatic_creative_theme(
                business=business,
                social_accounts=(
                    social_accounts
                ),
            )
        )
    except CreativeContextError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    return (
        map_automatic_creative_theme_response(
            internal_result
        )
    )


@router.post(
    "/auto-resolve",
    response_model=(
        AutomaticCreativeThemeResponse
    ),
    status_code=status.HTTP_200_OK,
    summary=(
        "Resolve automatic creative theme"
    ),
)
async def auto_resolve_creative_theme(
    business_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> AutomaticCreativeThemeResponse:
    """
    Return the full automatic creative-theme resolution.

    This response is intended for internal audit, diagnostics,
    administration, and explainability. It includes resolved and
    rejected moments, registry warnings, automatic provenance,
    and social-platform context.
    """

    return await _resolve_full_response(
        business_id=business_id,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/image-handoff",
    response_model=ImageGenerationHandoff,
    status_code=status.HTTP_200_OK,
    summary=(
        "Build image-generation handoff"
    ),
)
async def build_image_generation_handoff(
    business_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> ImageGenerationHandoff:
    """
    Return the compact contract consumed by image services.

    The response intentionally excludes:

    - Rejected moments.
    - Inactive moment candidates.
    - Registry warnings.
    - Social-account identifiers.
    - Internal automatic-context diagnostics.
    """

    full_response = await (
        _resolve_full_response(
            business_id=business_id,
            current_user=current_user,
            db=db,
        )
    )

    return map_image_generation_handoff(
        full_response
    )