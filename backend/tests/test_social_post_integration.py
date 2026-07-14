"""
Social Post MongoDB Integration Tests

Tests the SocialPostDocument against the development MongoDB
instance running in Docker.

The test verifies:

- Document insertion
- Normalized post content
- Business-level tenant isolation
- Social-account scoping
- Platform filtering
- Unique-index duplicate prevention
- Latest-metrics update
- Cleanup of temporary documents
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)


@pytest.mark.asyncio
async def test_social_post_storage_and_tenant_isolation():
    """
    Verify the complete SocialPostDocument persistence flow.

    Two business IDs and two social-account IDs are generated
    only for this test.

    No real PostgreSQL business or social account is modified.
    """

    business_a_id = uuid4()
    business_b_id = uuid4()

    social_account_a_id = uuid4()
    social_account_b_id = uuid4()

    unique_suffix = uuid4().hex
    platform_post_id = f"integration-post-{unique_suffix}"

    inserted_document_ids = []

    try:
        # ====================================================
        # Initialize MongoDB and Beanie
        # ====================================================
        await connect_to_mongo()

        # ====================================================
        # Insert Post for Business A
        # ====================================================
        post = SocialPostDocument(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
            platform="instagram",
            platform_post_id=platform_post_id,
            published_at=datetime.now(UTC),
            post_url=(
                "https://example.test/"
                f"posts/{platform_post_id}"
            ),
            content_type="image",
            text="Integration test social post",
            hashtags=[
                "integration",
                "testing",
            ],
            mentions=[
                "example_account",
            ],
            media_urls=[
                "https://example.test/media/image-1.jpg",
            ],
            language="en",
            latest_metrics=SocialPostMetrics(
                likes=120,
                comments=14,
                shares=5,
                saves=9,
                views=1000,
                reach=750,
                impressions=1200,
                captured_at=datetime.now(UTC),
            ),
            connector_type="apify",
            raw_data={
                "test_record": True,
                "source": "mongo_integration_test",
                "original_post_id": platform_post_id,
            },
        )

        await post.insert()

        inserted_document_ids.append(post.id)

        assert post.id is not None

        # ====================================================
        # Retrieve by Platform Identity
        # ====================================================
        stored_post = await SocialPostDocument.find_one(
            SocialPostDocument.platform == "instagram",
            SocialPostDocument.social_account_id
            == social_account_a_id,
            SocialPostDocument.platform_post_id
            == platform_post_id,
        )

        assert stored_post is not None
        assert stored_post.id == post.id

        assert stored_post.business_id == business_a_id

        assert (
            stored_post.social_account_id
            == social_account_a_id
        )

        assert stored_post.platform == "instagram"

        assert (
            stored_post.platform_post_id
            == platform_post_id
        )

        assert (
            stored_post.text
            == "Integration test social post"
        )

        assert stored_post.hashtags == [
            "integration",
            "testing",
        ]

        assert stored_post.latest_metrics.likes == 120
        assert stored_post.latest_metrics.comments == 14
        assert stored_post.latest_metrics.views == 1000

        assert stored_post.raw_data["test_record"] is True

        # ====================================================
        # Business A Can Query Its Post
        # ====================================================
        business_a_posts = await SocialPostDocument.find(
            SocialPostDocument.business_id == business_a_id
        ).to_list()

        assert len(business_a_posts) == 1
        assert business_a_posts[0].id == post.id

        # ====================================================
        # Business B Cannot Query Business A Post
        # ====================================================
        business_b_posts = await SocialPostDocument.find(
            SocialPostDocument.business_id == business_b_id
        ).to_list()

        assert business_b_posts == []

        cross_business_post = await SocialPostDocument.find_one(
            SocialPostDocument.business_id == business_b_id,
            SocialPostDocument.id == post.id,
        )

        assert cross_business_post is None

        # ====================================================
        # Different Social Account Cannot Query the Post
        # ====================================================
        wrong_account_post = await SocialPostDocument.find_one(
            SocialPostDocument.business_id == business_a_id,
            SocialPostDocument.social_account_id
            == social_account_b_id,
            SocialPostDocument.platform_post_id
            == platform_post_id,
        )

        assert wrong_account_post is None

        # ====================================================
        # Platform Filter Works
        # ====================================================
        instagram_posts = await SocialPostDocument.find(
            SocialPostDocument.business_id == business_a_id,
            SocialPostDocument.platform == "instagram",
        ).to_list()

        assert len(instagram_posts) == 1
        assert instagram_posts[0].id == post.id

        facebook_posts = await SocialPostDocument.find(
            SocialPostDocument.business_id == business_a_id,
            SocialPostDocument.platform == "facebook",
        ).to_list()

        assert facebook_posts == []

        # ====================================================
        # Duplicate Platform Identity Is Rejected
        # ====================================================
        duplicate_post = SocialPostDocument(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
            platform="instagram",
            platform_post_id=platform_post_id,
            text="Duplicate integration test post",
        )

        with pytest.raises(DuplicateKeyError):
            await duplicate_post.insert()

        # ====================================================
        # Update Latest Metrics
        # ====================================================
        stored_post.latest_metrics = SocialPostMetrics(
            likes=250,
            comments=31,
            shares=12,
            saves=20,
            views=2400,
            reach=1800,
            impressions=3000,
            captured_at=datetime.now(UTC),
        )

        stored_post.updated_at = datetime.now(UTC)

        await stored_post.save()

        updated_post = await SocialPostDocument.get(
            stored_post.id
        )

        assert updated_post is not None

        assert updated_post.latest_metrics.likes == 250
        assert updated_post.latest_metrics.comments == 31
        assert updated_post.latest_metrics.shares == 12
        assert updated_post.latest_metrics.views == 2400

        # Identity remains unchanged after metrics update.
        assert updated_post.business_id == business_a_id

        assert (
            updated_post.social_account_id
            == social_account_a_id
        )

        assert updated_post.platform == "instagram"

        assert (
            updated_post.platform_post_id
            == platform_post_id
        )

    finally:
        # ====================================================
        # Cleanup Temporary MongoDB Documents
        # ====================================================
        try:
            for document_id in inserted_document_ids:
                document = await SocialPostDocument.get(
                    document_id
                )

                if document is not None:
                    await document.delete()
        finally:
            await close_mongo()
