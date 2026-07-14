"""
Social Account Service Integration Tests

These tests use the development PostgreSQL database running in Docker.

Each test creates temporary user, business, and social-account records.
Temporary data is deleted in a finally block, even when an assertion fails.
"""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.postgres import async_session_maker
from app.models.pg.business import Business
from app.models.pg.social_account import SocialAccount
from app.models.pg.user import User
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountUpdate,
)
from app.services.social_account_service import (
    SocialAccountAlreadyExistsError,
    create_social_account,
    delete_social_account,
    get_social_account_by_id,
    get_social_account_by_platform_identity,
    list_social_accounts,
    update_social_account,
)


@pytest.mark.asyncio
async def test_social_account_service_crud_and_tenant_isolation():
    """
    Verify the complete SocialAccount service flow.

    Covered behavior:
    - Create temporary user and two businesses.
    - Create a social account under Business A.
    - Verify default values.
    - Verify Business A can list and retrieve the account.
    - Verify Business B cannot retrieve the account.
    - Reject a duplicate platform identity.
    - Update allowed fields.
    - Delete the social account.
    - Preserve both businesses.
    - Clean all temporary data.
    """

    unique_suffix = uuid4().hex

    temporary_user_id = None
    business_a_id = None
    business_b_id = None
    social_account_id = None

    async with async_session_maker() as db:
        try:
            # =================================================
            # Arrange: Create Temporary User
            # =================================================
            temporary_user = User(
                email=(
                    f"social-account-test-{unique_suffix}"
                    "@example.test"
                ),
                hashed_password="temporary-test-password-hash",
                full_name="Social Account Integration Test",
                is_active=True,
                is_verified=True,
                role="user",
            )

            db.add(temporary_user)
            await db.commit()
            await db.refresh(temporary_user)

            temporary_user_id = temporary_user.id

            # =================================================
            # Arrange: Create Two Temporary Businesses
            # =================================================
            business_a = Business(
                owner_id=temporary_user.id,
                name=f"Integration Business A {unique_suffix}",
                business_type="test_business",
                industry="testing",
                location="test-location",
                country_code="EG",
                business_metadata={
                    "test_record": True,
                },
                is_active=True,
            )

            business_b = Business(
                owner_id=temporary_user.id,
                name=f"Integration Business B {unique_suffix}",
                business_type="test_business",
                industry="testing",
                location="test-location",
                country_code="EG",
                business_metadata={
                    "test_record": True,
                },
                is_active=True,
            )

            db.add_all([business_a, business_b])
            await db.commit()
            await db.refresh(business_a)
            await db.refresh(business_b)

            business_a_id = business_a.id
            business_b_id = business_b.id

            # =================================================
            # Create Social Account Under Business A
            # =================================================
            create_payload = SocialAccountCreate(
                platform=" Instagram ",
                platform_account_id=(
                    f"integration-account-{unique_suffix}"
                ),
                account_name="Integration Test Account",
                account_username="@integration_test",
                account_url=(
                    "https://example.test/integration-account"
                ),
                connector_type=" APIFY ",
                account_metadata={
                    "test_record": True,
                    "source": "integration_test",
                },
            )

            created_account = await create_social_account(
                db=db,
                business_id=business_a.id,
                account_data=create_payload,
            )

            social_account_id = created_account.id

            # =================================================
            # Assert: Created Values and Defaults
            # =================================================
            assert created_account.business_id == business_a.id
            assert created_account.platform == "instagram"

            assert (
                created_account.platform_account_id
                == f"integration-account-{unique_suffix}"
            )

            assert (
                created_account.account_name
                == "Integration Test Account"
            )

            assert created_account.connector_type == "apify"
            assert created_account.credential_reference is None
            assert created_account.is_active is True

            assert (
                created_account.connection_status
                == "pending"
            )

            assert created_account.connected_at is None

            # =================================================
            # Assert: Platform Identity Lookup
            # =================================================
            identity_result = (
                await get_social_account_by_platform_identity(
                    db=db,
                    platform="INSTAGRAM",
                    platform_account_id=(
                        f"integration-account-{unique_suffix}"
                    ),
                )
            )

            assert identity_result is not None
            assert identity_result.id == created_account.id

            # =================================================
            # Assert: Business A Can List Its Account
            # =================================================
            business_a_accounts, business_a_total = (
                await list_social_accounts(
                    db=db,
                    business_id=business_a.id,
                )
            )

            assert business_a_total == 1

            assert [
                account.id
                for account in business_a_accounts
            ] == [created_account.id]

            # =================================================
            # Assert: Platform Filter Works
            # =================================================
            filtered_accounts, filtered_total = (
                await list_social_accounts(
                    db=db,
                    business_id=business_a.id,
                    platform=" INSTAGRAM ",
                    is_active=True,
                )
            )

            assert filtered_total == 1
            assert len(filtered_accounts) == 1
            assert filtered_accounts[0].id == created_account.id

            # =================================================
            # Assert: Business B Cannot See Business A Account
            # =================================================
            business_b_accounts, business_b_total = (
                await list_social_accounts(
                    db=db,
                    business_id=business_b.id,
                )
            )

            assert business_b_total == 0
            assert business_b_accounts == []

            cross_business_result = (
                await get_social_account_by_id(
                    db=db,
                    business_id=business_b.id,
                    account_id=created_account.id,
                )
            )

            assert cross_business_result is None

            # =================================================
            # Assert: Business A Can Retrieve Its Account
            # =================================================
            business_a_result = await get_social_account_by_id(
                db=db,
                business_id=business_a.id,
                account_id=created_account.id,
            )

            assert business_a_result is not None
            assert business_a_result.id == created_account.id

            # =================================================
            # Assert: Duplicate Identity Is Rejected
            # =================================================
            duplicate_payload = SocialAccountCreate(
                platform="instagram",
                platform_account_id=(
                    f"integration-account-{unique_suffix}"
                ),
                account_name="Duplicate Integration Account",
            )

            with pytest.raises(
                SocialAccountAlreadyExistsError
            ):
                await create_social_account(
                    db=db,
                    business_id=business_b.id,
                    account_data=duplicate_payload,
                )

            # =================================================
            # Update Allowed Fields
            # =================================================
            update_payload = SocialAccountUpdate(
                account_name="Updated Integration Account",
                account_username="@updated_integration",
                account_url=None,
                connector_type=" OFFICIAL_API ",
                account_metadata={
                    "test_record": True,
                    "updated": True,
                },
                is_active=False,
            )

            updated_account = await update_social_account(
                db=db,
                account=created_account,
                update_data=update_payload,
            )

            assert (
                updated_account.account_name
                == "Updated Integration Account"
            )

            assert (
                updated_account.account_username
                == "@updated_integration"
            )

            assert updated_account.account_url is None

            assert (
                updated_account.connector_type
                == "official_api"
            )

            assert updated_account.account_metadata == {
                "test_record": True,
                "updated": True,
            }

            assert updated_account.is_active is False

            # Identity must remain unchanged.
            assert updated_account.platform == "instagram"

            assert (
                updated_account.platform_account_id
                == f"integration-account-{unique_suffix}"
            )

            # =================================================
            # Delete Social Account
            # =================================================
            await delete_social_account(
                db=db,
                account=updated_account,
            )

            deleted_account = await get_social_account_by_id(
                db=db,
                business_id=business_a.id,
                account_id=social_account_id,
            )

            assert deleted_account is None

            # =================================================
            # Assert: Businesses Were Not Deleted
            # =================================================
            businesses_result = await db.execute(
                select(Business.id).where(
                    Business.id.in_(
                        [business_a.id, business_b.id]
                    )
                )
            )

            remaining_business_ids = set(
                businesses_result.scalars().all()
            )

            assert remaining_business_ids == {
                business_a.id,
                business_b.id,
            }

        finally:
            # =================================================
            # Cleanup Temporary Records
            # =================================================
            await db.rollback()

            if social_account_id is not None:
                await db.execute(
                    delete(SocialAccount).where(
                        SocialAccount.id == social_account_id
                    )
                )

            if temporary_user_id is not None:
                # Deleting the temporary user cascades to both
                # temporary businesses and any remaining related
                # PostgreSQL records.
                await db.execute(
                    delete(User).where(
                        User.id == temporary_user_id
                    )
                )

            await db.commit()