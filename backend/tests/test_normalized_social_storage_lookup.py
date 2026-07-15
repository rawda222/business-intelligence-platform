"""
Normalized Social Storage Lookup Tests

Verifies tenant-scoped lookup of normalized social posts.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)
from app.services.normalized_social_storage_service import (
    find_existing_normalized_post,
)


@pytest.mark.asyncio
async def test_normalized_post_lookup_preserves_tenant_scope():
    """
    Match a post only inside the exact business, account,
    platform, and platform-post scope.
    """

    business_a_id = uuid4()
    business_b_id = uuid4()

    social_account_a_id = uuid4()
    social_account_b_id = uuid4()

    platform_post_id = (
        f"lookup-test-{uuid4().hex}"
    )

    stored_post = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=datetime.now(UTC),
            text="Normalized storage lookup test",
        )

        await stored_post.insert()

        matching_normalized_post = NormalizedSocialPost(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=datetime.now(UTC),
            text="Updated normalized post text",
            content_type="text",
            metrics=NormalizedSocialMetrics(
                reactions=74,
                comments=8,
                captured_at=datetime.now(UTC),
            ),
            connector_type="apify",
        )

        match = await find_existing_normalized_post(
            matching_normalized_post
        )

        assert match is not None
        assert match.id == stored_post.id

        # Different business must not match.
        different_business_post = (
            matching_normalized_post.model_copy(
                update={
                    "business_id": business_b_id,
                },
            )
        )

        assert (
            await find_existing_normalized_post(
                different_business_post
            )
            is None
        )

        # Different social account must not match.
        different_account_post = (
            matching_normalized_post.model_copy(
                update={
                    "social_account_id": (
                        social_account_b_id
                    ),
                },
            )
        )

        assert (
            await find_existing_normalized_post(
                different_account_post
            )
            is None
        )

        # Different platform must not match.
        different_platform_post = (
            matching_normalized_post.model_copy(
                update={
                    "platform": "instagram",
                },
            )
        )

        assert (
            await find_existing_normalized_post(
                different_platform_post
            )
            is None
        )

        # Different external post ID must not match.
        different_external_id_post = (
            matching_normalized_post.model_copy(
                update={
                    "platform_post_id": (
                        "DifferentPostID"
                    ),
                },
            )
        )

        assert (
            await find_existing_normalized_post(
                different_external_id_post
            )
            is None
        )

    finally:
        try:
            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                persisted_post = (
                    await SocialPostDocument.get(
                        stored_post.id,
                    )
                )

                if persisted_post is not None:
                    await persisted_post.delete()
        finally:
            await close_mongo()
