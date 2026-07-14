"""
Social Accounts API Integration Tests

Tests the complete HTTP flow for social-account management:

- Authentication protection
- Business ownership verification
- Account creation
- Duplicate prevention
- Tenant isolation
- Pagination and filtering
- Validation
- Update
- Delete
- Cleanup

The tests use temporary PostgreSQL records and remove them
after execution.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.dependencies import get_current_user
from app.db.postgres import async_session_maker
from app.main import app
from app.models.pg.business import Business
from app.models.pg.user import User


@pytest.mark.asyncio
async def test_social_accounts_api_crud_and_tenant_isolation():
    """
    Verify the complete secured Social Accounts API flow.

    Two users are created:

    - User A owns Business A.
    - User B owns Business B.

    The test verifies that neither user can access the other
    user's business or social accounts.
    """

    unique_suffix = uuid4().hex

    user_a_id = None
    user_b_id = None

    business_a_id = None
    business_b_id = None

    selected_user = {
        "value": None,
    }

    # ========================================================
    # Dependency Override
    # ========================================================
    async def override_get_current_user():
        """Return the user selected by the current test step."""

        return selected_user["value"]

    # ========================================================
    # Arrange: Create Temporary Users and Businesses
    # ========================================================
    async with async_session_maker() as db:
        user_a = User(
            email=(
                f"social-api-owner-a-{unique_suffix}"
                "@example.test"
            ),
            hashed_password="temporary-test-password-hash",
            full_name="Social API Owner A",
            is_active=True,
            is_verified=True,
            role="user",
        )

        user_b = User(
            email=(
                f"social-api-owner-b-{unique_suffix}"
                "@example.test"
            ),
            hashed_password="temporary-test-password-hash",
            full_name="Social API Owner B",
            is_active=True,
            is_verified=True,
            role="user",
        )

        db.add_all([user_a, user_b])
        await db.commit()

        await db.refresh(user_a)
        await db.refresh(user_b)

        user_a_id = user_a.id
        user_b_id = user_b.id

        business_a = Business(
            owner_id=user_a.id,
            name=f"Social API Business A {unique_suffix}",
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
            owner_id=user_b.id,
            name=f"Social API Business B {unique_suffix}",
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

        selected_user["value"] = user_a

    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            # =================================================
            # Authentication Protection
            # =================================================
            app.dependency_overrides.pop(
                get_current_user,
                None,
            )

            unauthenticated_response = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                )
            )

            # HTTPBearer may return 401 or 403 for missing
            # credentials depending on the FastAPI version.
            assert unauthenticated_response.status_code in {
                401,
                403,
            }

            # Enable controlled authentication for the rest
            # of the test.
            app.dependency_overrides[
                get_current_user
            ] = override_get_current_user

            selected_user["value"] = user_a

            # =================================================
            # Create Social Account Under Business A
            # =================================================
            create_payload = {
                "platform": " Instagram ",
                "platform_account_id": (
                    f"api-account-{unique_suffix}"
                ),
                "account_name": "API Integration Account",
                "account_username": "@api_integration",
                "account_url": (
                    "https://example.test/api-integration"
                ),
                "connector_type": " APIFY ",
                "account_metadata": {
                    "test_record": True,
                    "source": "api_integration_test",
                },
            }

            create_response = await client.post(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                ),
                json=create_payload,
            )

            assert create_response.status_code == 201

            created_data = create_response.json()

            account_id = created_data["id"]

            assert (
                created_data["business_id"]
                == str(business_a_id)
            )

            assert created_data["platform"] == "instagram"

            assert (
                created_data["platform_account_id"]
                == f"api-account-{unique_suffix}"
            )

            assert (
                created_data["account_name"]
                == "API Integration Account"
            )

            assert (
                created_data["connector_type"]
                == "apify"
            )

            assert created_data["is_active"] is True

            assert (
                created_data["connection_status"]
                == "pending"
            )

            assert created_data["connected_at"] is None

            assert (
                "credential_reference"
                not in created_data
            )

            # =================================================
            # Duplicate Identity Returns 409
            # =================================================
            duplicate_response = await client.post(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                ),
                json={
                    "platform": "instagram",
                    "platform_account_id": (
                        f"api-account-{unique_suffix}"
                    ),
                    "account_name": "Duplicate Account",
                },
            )

            assert duplicate_response.status_code == 409

            # =================================================
            # List Business A Accounts
            # =================================================
            list_response = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                ),
                params={
                    "page": 1,
                    "page_size": 20,
                    "platform": " INSTAGRAM ",
                    "is_active": True,
                },
            )

            assert list_response.status_code == 200

            list_data = list_response.json()

            assert list_data["total"] == 1
            assert list_data["page"] == 1
            assert list_data["page_size"] == 20
            assert list_data["total_pages"] == 1
            assert len(list_data["items"]) == 1

            assert (
                list_data["items"][0]["id"]
                == account_id
            )

            assert (
                "credential_reference"
                not in list_data["items"][0]
            )

            # =================================================
            # Get Account Under Correct Business
            # =================================================
            get_response = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                )
            )

            assert get_response.status_code == 200

            get_data = get_response.json()

            assert get_data["id"] == account_id
            assert (
                get_data["business_id"]
                == str(business_a_id)
            )

            # =================================================
            # User B Cannot Access Business A
            # =================================================
            selected_user["value"] = user_b

            forbidden_business_list = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                )
            )

            assert forbidden_business_list.status_code == 404

            assert forbidden_business_list.json() == {
                "detail": "Business not found",
            }

            forbidden_business_account = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                )
            )

            assert (
                forbidden_business_account.status_code
                == 404
            )

            # =================================================
            # User B Cannot Place Account A Under Business B
            # =================================================
            wrong_business_account = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_b_id}/social-accounts/"
                    f"{account_id}"
                )
            )

            assert wrong_business_account.status_code == 404

            assert wrong_business_account.json() == {
                "detail": "Social account not found",
            }

            # =================================================
            # Return to User A
            # =================================================
            selected_user["value"] = user_a

            # =================================================
            # Reject Server-Controlled Fields
            # =================================================
            invalid_create_response = await client.post(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                ),
                json={
                    "platform": "facebook",
                    "platform_account_id": (
                        f"server-fields-{unique_suffix}"
                    ),
                    "account_name": "Invalid Account",
                    "business_id": str(business_b_id),
                    "connection_status": "connected",
                },
            )

            assert invalid_create_response.status_code == 422

            # =================================================
            # Reject Platform Identity Update
            # =================================================
            identity_update_response = await client.patch(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                ),
                json={
                    "platform_account_id": (
                        "different-platform-account"
                    ),
                },
            )

            assert identity_update_response.status_code == 422

            # =================================================
            # Update Allowed Fields
            # =================================================
            update_response = await client.patch(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                ),
                json={
                    "account_name": (
                        "Updated API Integration Account"
                    ),
                    "account_username": (
                        "@updated_api_integration"
                    ),
                    "account_url": None,
                    "connector_type": " OFFICIAL_API ",
                    "account_metadata": {
                        "test_record": True,
                        "updated": True,
                    },
                    "is_active": False,
                },
            )

            assert update_response.status_code == 200

            updated_data = update_response.json()

            assert (
                updated_data["account_name"]
                == "Updated API Integration Account"
            )

            assert (
                updated_data["account_username"]
                == "@updated_api_integration"
            )

            assert updated_data["account_url"] is None

            assert (
                updated_data["connector_type"]
                == "official_api"
            )

            assert updated_data["account_metadata"] == {
                "test_record": True,
                "updated": True,
            }

            assert updated_data["is_active"] is False

            # Platform identity remains unchanged.
            assert updated_data["platform"] == "instagram"

            assert (
                updated_data["platform_account_id"]
                == f"api-account-{unique_suffix}"
            )

            assert (
                "credential_reference"
                not in updated_data
            )

            # =================================================
            # Delete Social Account
            # =================================================
            delete_response = await client.delete(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                )
            )

            assert delete_response.status_code == 200

            delete_data = delete_response.json()

            assert delete_data["success"] is True

            # =================================================
            # Deleted Account Returns 404
            # =================================================
            deleted_get_response = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts/"
                    f"{account_id}"
                )
            )

            assert deleted_get_response.status_code == 404

            empty_list_response = await client.get(
                (
                    "/api/v1/businesses/"
                    f"{business_a_id}/social-accounts"
                )
            )

            assert empty_list_response.status_code == 200

            empty_list_data = empty_list_response.json()

            assert empty_list_data["total"] == 0
            assert empty_list_data["items"] == []
            assert empty_list_data["total_pages"] == 0

    finally:
        # =====================================================
        # Remove Dependency Overrides
        # =====================================================
        app.dependency_overrides.clear()

        # =====================================================
        # Cleanup Temporary PostgreSQL Records
        # =====================================================
        async with async_session_maker() as cleanup_db:
            await cleanup_db.rollback()

            temporary_user_ids = [
                user_id
                for user_id in [user_a_id, user_b_id]
                if user_id is not None
            ]

            if temporary_user_ids:
                await cleanup_db.execute(
                    delete(User).where(
                        User.id.in_(temporary_user_ids)
                    )
                )

            await cleanup_db.commit()