"""
Normalized Social Storage Creation Tests

Verifies creation of MongoDB social posts from normalized,
platform-independent post contracts.
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
    create_normalized_social_post,
)


@pytest.mark.asyncio
async def test_create_normalized_social_post():
    """
    Create a MongoDB post while preserving normalized content.

    Metrics are not assigned directly to latest_metrics because
    historical metric persistence belongs to PostMetricService.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    unique_suffix = uuid4().hex

    captured_at = datetime(
        2026,
        7,
        15,
        9,
        0,
        tzinfo=UTC,
    )

    published_at = datetime(
        2026,
        7,
        14,
        18,
        0,
        tzinfo=UTC,
    )

    created_post = None

    try:
        await connect_to_mongo()

        normalized_post = NormalizedSocialPost(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="instagram",
            platform_post_id=(
                f"CreateCaseSensitive{unique_suffix}"
            ),
            published_at=published_at,
            post_url=(
                "https://example.test/"
                "normalized-instagram-post"
            ),
            content_type="carousel",
            text="Normalized storage creation test",
            hashtags=[
                "Fashion",
                "Available",
            ],
            mentions=[
                "example_account",
            ],
            tagged_accounts=[
                "model_account",
            ],
            media_urls=[
                "https://example.test/image-1.jpg",
                "https://example.test/image-2.jpg",
            ],
            language="en",
            location_name="Test Location",
            is_pinned=False,
            metrics=NormalizedSocialMetrics(
                likes=105,
                comments=4,
                captured_at=captured_at,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "instagram",
                "source_post_id": (
                    f"CreateCaseSensitive{unique_suffix}"
                ),
            },
        )

        created_post = (
            await create_normalized_social_post(
                normalized_post
            )
        )

        assert created_post.id is not None
        assert created_post.business_id == business_id

        assert (
            created_post.social_account_id
            == social_account_id
        )

        assert created_post.platform == "instagram"

        assert (
            created_post.platform_post_id
            == normalized_post.platform_post_id
        )

        assert created_post.published_at is not None
        assert created_post.post_url == (
            "https://example.test/"
            "normalized-instagram-post"
        )

        assert created_post.content_type == "carousel"

        assert (
            created_post.text
            == "Normalized storage creation test"
        )

        assert created_post.hashtags == [
            "Fashion",
            "Available",
        ]

        assert created_post.mentions == [
            "example_account",
        ]

        assert created_post.media_urls == [
            "https://example.test/image-1.jpg",
            "https://example.test/image-2.jpg",
        ]

        assert created_post.language == "en"
        assert created_post.connector_type == "apify"

        assert created_post.raw_data == {
            "source_platform": "instagram",
            "source_post_id": (
                normalized_post.platform_post_id
            ),
            "tagged_accounts": [
                "model_account",
            ],
            "location_name": "Test Location",
            "is_pinned": False,
        }

        assert created_post.collected_at == captured_at

        # Metric history is intentionally handled separately.
        assert created_post.latest_metrics.likes is None
        assert created_post.latest_metrics.reactions is None
        assert created_post.latest_metrics.comments is None

        stored_post = await SocialPostDocument.get(
            created_post.id,
        )

        assert stored_post is not None

        assert (
            stored_post.platform_post_id
            == normalized_post.platform_post_id
        )

        assert stored_post.raw_data[
            "tagged_accounts"
        ] == [
            "model_account",
        ]

    finally:
        try:
            if (
                created_post is not None
                and created_post.id is not None
            ):
                stored_post = (
                    await SocialPostDocument.get(
                        created_post.id,
                    )
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()