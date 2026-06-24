"""
Business Service
Business logic for managing businesses (CRUD operations).
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.pg.business import Business
from app.schemas.business import BusinessCreate, BusinessUpdate


# ============================================================
# Create Business
# ============================================================
async def create_business(
    db: AsyncSession,
    business_data: BusinessCreate,
    owner_id: UUID,
) -> Business:
    """
    Create a new business owned by the current user.
    
    Args:
        db: Database session
        business_data: Business creation data
        owner_id: UUID of the owner (from authenticated user)
    
    Returns:
        Created Business object
    """
    new_business = Business(
        owner_id=owner_id,
        name=business_data.name,
        business_type=business_data.business_type,
        industry=business_data.industry,
        location=business_data.location,
        country_code=business_data.country_code,
        business_metadata=business_data.business_metadata,
        is_active=True,
    )
    
    db.add(new_business)
    await db.commit()
    await db.refresh(new_business)
    
    return new_business


# ============================================================
# List Businesses (for current user)
# ============================================================
async def list_user_businesses(
    db: AsyncSession,
    owner_id: UUID,
    skip: int = 0,
    limit: int = 50,
    business_type: str | None = None,
) -> tuple[list[Business], int]:
    """
    List all businesses owned by the current user.
    
    Args:
        db: Database session
        owner_id: UUID of the owner
        skip: Pagination offset
        limit: Max results per page
        business_type: Optional filter by business type
    
    Returns:
        Tuple of (businesses list, total count)
    """
    # Build query
    query = select(Business).where(Business.owner_id == owner_id)
    
    if business_type:
        query = query.where(Business.business_type == business_type)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get paginated results
    query = query.order_by(Business.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    businesses = list(result.scalars().all())
    
    return businesses, total


# ============================================================
# Get Business by ID (with ownership check)
# ============================================================
async def get_business_by_id(
    db: AsyncSession,
    business_id: UUID,
    owner_id: UUID,
) -> Business | None:
    """
    Get a business by ID, ensuring it belongs to the current user.
    
    Args:
        db: Database session
        business_id: UUID of the business
        owner_id: UUID of the owner (for security check)
    
    Returns:
        Business object or None (if not found or not owned)
    """
    result = await db.execute(
        select(Business).where(
            Business.id == business_id,
            Business.owner_id == owner_id,  # 🔒 Multi-tenant security!
        )
    )
    return result.scalar_one_or_none()


# ============================================================
# Update Business
# ============================================================
async def update_business(
    db: AsyncSession,
    business: Business,
    update_data: BusinessUpdate,
) -> Business:
    """
    Update business fields (partial update).
    
    Args:
        db: Database session
        business: Business object to update
        update_data: Fields to update
    
    Returns:
        Updated Business object
    """
    # Get only the fields that were provided (exclude unset)
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Update fields
    for field, value in update_dict.items():
        setattr(business, field, value)
    
    await db.commit()
    await db.refresh(business)
    
    return business


# ============================================================
# Delete Business
# ============================================================
async def delete_business(
    db: AsyncSession,
    business: Business,
) -> None:
    """
    Delete a business.
    All related reports and initiatives are deleted via CASCADE.
    """
    await db.delete(business)
    await db.commit()