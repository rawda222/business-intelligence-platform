"""
Social Account Service

Business logic for managing social media accounts connected
to businesses.

All account queries are scoped by business_id to preserve
multi-tenant data isolation.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pg.social_account import SocialAccount
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountUpdate,
)


# ============================================================
# Service Exceptions
# ============================================================
class SocialAccountAlreadyExistsError(Exception):
    """
    Raised when the same platform account is already connected.

    The database unique constraint remains the final protection
    against concurrent duplicate requests.
    """


# ============================================================
# Create Social Account
# ============================================================
async def create_social_account(
    db: AsyncSession,
    business_id: UUID,
    account_data: SocialAccountCreate,
) -> SocialAccount:
    """
    Create a social account under a verified business.

    Business ownership must be checked by the API layer before
    this function is called.
    """

    existing_account = await get_social_account_by_platform_identity(
        db=db,
        platform=account_data.platform,
        platform_account_id=account_data.platform_account_id,
    )

    if existing_account:
        raise SocialAccountAlreadyExistsError(
            "This social media account is already connected."
        )

    new_account = SocialAccount(
        business_id=business_id,
        platform=account_data.platform,
        platform_account_id=account_data.platform_account_id,
        account_name=account_data.account_name,
        account_username=account_data.account_username,
        account_url=account_data.account_url,
        connector_type=account_data.connector_type,
        credential_reference=None,
        account_metadata=account_data.account_metadata,
        is_active=True,
        connection_status="pending",
        connected_at=None,
    )

    db.add(new_account)

    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()

        raise SocialAccountAlreadyExistsError(
            "This social media account is already connected."
        ) from error

    await db.refresh(new_account)

    return new_account


# ============================================================
# List Social Accounts
# ============================================================
async def list_social_accounts(
    db: AsyncSession,
    business_id: UUID,
    skip: int = 0,
    limit: int = 50,
    platform: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[SocialAccount], int]:
    """
    List social accounts belonging to one business.

    Optional filters:
    - platform
    - active status
    """

    query = select(SocialAccount).where(
        SocialAccount.business_id == business_id
    )

    if platform:
        query = query.where(
            SocialAccount.platform == platform.strip().lower()
        )

    if is_active is not None:
        query = query.where(
            SocialAccount.is_active == is_active
        )

    count_query = select(func.count()).select_from(
        query.subquery()
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query
        .order_by(SocialAccount.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    accounts = list(result.scalars().all())

    return accounts, total


# ============================================================
# Get Social Account by ID
# ============================================================
async def get_social_account_by_id(
    db: AsyncSession,
    business_id: UUID,
    account_id: UUID,
) -> SocialAccount | None:
    """
    Get one social account scoped to a specific business.

    Scoping by both IDs prevents a social account belonging to
    another business from being returned.
    """

    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.business_id == business_id,
        )
    )

    return result.scalar_one_or_none()


# ============================================================
# Get by Platform Identity
# ============================================================
async def get_social_account_by_platform_identity(
    db: AsyncSession,
    platform: str,
    platform_account_id: str,
) -> SocialAccount | None:
    """
    Find an account using its stable platform identity.

    This query is intentionally global because the database
    prevents the same real platform account from being assigned
    to multiple businesses.
    """

    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.platform == platform.strip().lower(),
            SocialAccount.platform_account_id
            == platform_account_id,
        )
    )

    return result.scalar_one_or_none()


# ============================================================
# Update Social Account
# ============================================================
async def update_social_account(
    db: AsyncSession,
    account: SocialAccount,
    update_data: SocialAccountUpdate,
) -> SocialAccount:
    """
    Partially update editable social account fields.

    Platform and platform_account_id are absent from the update
    schema and therefore cannot be changed.
    """

    update_values = update_data.model_dump(
        exclude_unset=True
    )

    non_nullable_fields = {
        "account_name",
        "connector_type",
        "account_metadata",
        "is_active",
    }

    for field_name in non_nullable_fields:
        if (
            field_name in update_values
            and update_values[field_name] is None
        ):
            raise ValueError(
                f"{field_name} cannot be null"
            )

    for field_name, value in update_values.items():
        setattr(account, field_name, value)

    await db.commit()
    await db.refresh(account)

    return account


# ============================================================
# Delete Social Account
# ============================================================
async def delete_social_account(
    db: AsyncSession,
    account: SocialAccount,
) -> None:
    """
    Delete a social account record from PostgreSQL.

    Social post retention and MongoDB cleanup will be handled by
    a separate cleanup policy before collection is implemented.
    """

    await db.delete(account)
    await db.commit()