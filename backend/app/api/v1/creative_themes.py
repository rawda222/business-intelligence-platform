"""
Automatic Creative Theme Endpoints

Resolves an image-team creative-theme contract from business data
without requiring campaign context from the user.

Every request:

- Requires an authenticated user.
- Verifies business ownership.
- Loads active social accounts scoped to the business.
- Builds campaign context automatically.
- Returns provenance for every automatic decision.
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
from app.creative_context.response_mapper import (
    map_automatic_creative_theme_response,
)
from app.creative_context.schemas import (
    AutomaticCreativeThemeResponse,
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
    Resolve a creative theme using business-owned data.

    No campaign request body is required. The system derives:

    - Target country from the business profile.
    - Campaign date from the country timezone.
    - Platform from active connected social accounts.
    - Content format from platform policy.
    - Objective from the current safe policy.
    - Product context from industry or business type.

    A 404 response is returned for both missing businesses and
    businesses owned by another tenant.
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