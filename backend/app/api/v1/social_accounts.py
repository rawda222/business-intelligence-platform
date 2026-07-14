"""
Social Account Endpoints

CRUD operations for social media accounts connected to businesses.

Every endpoint verifies:
1. The authenticated user owns the requested business.
2. The requested social account belongs to that business.
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountResponse,
    SocialAccountUpdate,
)
from app.services.business_service import get_business_by_id
from app.services.social_account_service import (
    SocialAccountAlreadyExistsError,
    create_social_account,
    delete_social_account,
    get_social_account_by_id,
    list_social_accounts,
    update_social_account,
)


router = APIRouter(
    prefix="/businesses/{business_id}/social-accounts",
    tags=["Social Accounts"],
)


# ============================================================
# Internal Authorization Helpers
# ============================================================
async def verify_business_ownership(
    *,
    db: AsyncSession,
    business_id: UUID,
    current_user: User,
):
    """
    Verify that the requested business belongs to the current user.

    A 404 response is used for both:
    - A business that does not exist.
    - A business owned by another user.

    This avoids revealing whether another tenant's business exists.
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

    return business


async def get_business_social_account_or_404(
    *,
    db: AsyncSession,
    business_id: UUID,
    account_id: UUID,
):
    """
    Retrieve a social account scoped to one business.

    A social account belonging to another business is treated as
    not found to preserve tenant isolation.
    """

    account = await get_social_account_by_id(
        db=db,
        business_id=business_id,
        account_id=account_id,
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )

    return account


# ============================================================
# POST /businesses/{business_id}/social-accounts
# ============================================================
@router.post(
    "",
    response_model=SocialAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a social media account",
)
async def connect_social_account(
    business_id: UUID,
    account_data: SocialAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect a social media account to a business.

    The account starts with connection_status="pending".
    A future connector workflow will validate the external account
    before changing its status to "connected".
    """

    await verify_business_ownership(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    try:
        account = await create_social_account(
            db=db,
            business_id=business_id,
            account_data=account_data,
        )
    except SocialAccountAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return account


# ============================================================
# GET /businesses/{business_id}/social-accounts
# ============================================================
@router.get(
    "",
    response_model=PaginatedResponse[SocialAccountResponse],
    summary="List business social accounts",
)
async def list_business_social_accounts(
    business_id: UUID,
    page: int = Query(
        default=1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    ),
    platform: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
        description="Filter by social media platform",
    ),
    is_active: bool | None = Query(
        default=None,
        description="Filter by active status",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List social media accounts belonging to one business.

    Supports:
    - Pagination
    - Platform filtering
    - Active-status filtering
    """

    await verify_business_ownership(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    skip = (page - 1) * page_size

    accounts, total = await list_social_accounts(
        db=db,
        business_id=business_id,
        skip=skip,
        limit=page_size,
        platform=platform,
        is_active=is_active,
    )

    total_pages = (
        (total + page_size - 1) // page_size
        if total > 0
        else 0
    )

    items = [
        SocialAccountResponse.model_validate(account)
        for account in accounts
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ============================================================
# GET /businesses/{business_id}/social-accounts/{account_id}
# ============================================================
@router.get(
    "/{account_id}",
    response_model=SocialAccountResponse,
    summary="Get social account details",
)
async def get_business_social_account(
    business_id: UUID,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return one social account belonging to the requested business.
    """

    await verify_business_ownership(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    account = await get_business_social_account_or_404(
        db=db,
        business_id=business_id,
        account_id=account_id,
    )

    return account


# ============================================================
# PATCH /businesses/{business_id}/social-accounts/{account_id}
# ============================================================
@router.patch(
    "/{account_id}",
    response_model=SocialAccountResponse,
    summary="Update a social account",
)
async def update_business_social_account(
    business_id: UUID,
    account_id: UUID,
    update_data: SocialAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update editable social-account fields.

    Platform identity cannot be changed through this endpoint.
    """

    await verify_business_ownership(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    account = await get_business_social_account_or_404(
        db=db,
        business_id=business_id,
        account_id=account_id,
    )

    try:
        updated_account = await update_social_account(
            db=db,
            account=account,
            update_data=update_data,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return updated_account


# ============================================================
# DELETE /businesses/{business_id}/social-accounts/{account_id}
# ============================================================
@router.delete(
    "/{account_id}",
    response_model=SuccessResponse,
    summary="Delete a social account",
)
async def delete_business_social_account(
    business_id: UUID,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a social-account connection from PostgreSQL.

    Social-media content retention will be handled by a separate
    cleanup policy before data collection is implemented.
    """

    await verify_business_ownership(
        db=db,
        business_id=business_id,
        current_user=current_user,
    )

    account = await get_business_social_account_or_404(
        db=db,
        business_id=business_id,
        account_id=account_id,
    )

    account_name = account.account_name

    await delete_social_account(
        db=db,
        account=account,
    )

    return SuccessResponse(
        success=True,
        message=(
            f"Social account '{account_name}' "
            "deleted successfully"
        ),
    )