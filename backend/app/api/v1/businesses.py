"""
Business Endpoints
CRUD operations for businesses (multi-tenant secured).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessResponse,
    BusinessType,
)
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.services.business_service import (
    create_business,
    list_user_businesses,
    get_business_by_id,
    update_business,
    delete_business,
)


router = APIRouter(prefix="/businesses", tags=["Businesses"])


# ============================================================
# POST /businesses — Create a new business
# ============================================================
@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business",
)
async def create_new_business(
    business_data: BusinessCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new business owned by the current user.
    
    - **name**: Business name (required)
    - **business_type**: One of: food_and_beverage, saas, retail, b2b_services, hospitality
    - **industry**: Optional industry tag
    - **location**: Optional location
    - **country_code**: Optional ISO country code (2 chars)
    """
    business = await create_business(
        db=db,
        business_data=business_data,
        owner_id=current_user.id,
    )
    return business


# ============================================================
# GET /businesses — List user's businesses (paginated)
# ============================================================
@router.get(
    "",
    response_model=PaginatedResponse[BusinessResponse],
    summary="List my businesses",
)
async def list_my_businesses(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    business_type: BusinessType | None = Query(None, description="Filter by type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all businesses owned by the current user.
    Supports pagination and filtering by business_type.
    """
    skip = (page - 1) * page_size
    
    businesses, total = await list_user_businesses(
        db=db,
        owner_id=current_user.id,
        skip=skip,
        limit=page_size,
        business_type=business_type,
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    items = [BusinessResponse.model_validate(b) for b in businesses]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ============================================================
# GET /businesses/{id} — Get one business
# ============================================================
@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Get business details",
)
async def get_business(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific business.
    Returns 404 if the business doesn't exist or doesn't belong to you.
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


# ============================================================
# PATCH /businesses/{id} — Update business
# ============================================================
@router.patch(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Update business",
)
async def update_my_business(
    business_id: UUID,
    update_data: BusinessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update a business.
    Only the fields you send will be updated.
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
    
    updated = await update_business(db, business, update_data)
    return updated


# ============================================================
# DELETE /businesses/{id} — Delete business
# ============================================================
@router.delete(
    "/{business_id}",
    response_model=SuccessResponse,
    summary="Delete business",
)
async def delete_my_business(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a business permanently.
    All associated reports and initiatives will be deleted (CASCADE).
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
    
    business_name = business.name
    await delete_business(db, business)
    
    return SuccessResponse(
        success=True,
        message=f"Business '{business_name}' deleted successfully",
    )