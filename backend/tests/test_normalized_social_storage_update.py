"""
Normalized Social Storage Update Tests

Verifies safe updates of existing MongoDB social posts from
normalized post contracts.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)
from app.schemas.normalized_social import (
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)
from app.services.normalized_social_storage_service import (
    update_normalized_social_post_content,
)

from app.services.post_metric_service import (
    ensure_utc,
)

@pytest.mark.asyncio
async def test_existing_post_content_is_updated_safely():
    """
    Update useful incoming content while preserving stored values
    when the incoming normalized fields are empty or missing.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    unique_suffix = uuid4().hex

    original_collected_at = datetime(
        2026,
        7,
        14,
        9,
        0,
        tzinfo=UTC,
    )

    newer_collected_at = (
        original_collected_at
        + timedelta(hours=2)
    )

    stored_post = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="instagram",
            platform_post_id=(
                f"update-test-{unique_suffix}"
            ),
            published_at=datetime(
                2026,
                7,
                13,
                18,
                0,
                tzinfo=UTC,
            ),
            post_url=(
                "https://example.test/original-post"
            ),
            content_type="image",
            text="Original stored caption",
            hashtags=[
                "Original",
                "Fashion",
            ],
            mentions=[
                "original_account",
            ],
            media_urls=[
                "https://example.test/original.jpg",
            ],
            language="en",
            latest_metrics=SocialPostMetrics(
                likes=50,
                comments=2,
                captured_at=original_collected_at,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "instagram",
                "preserved_key": "preserved_value",
            },
            collected_at=original_collected_at,
        )

        await stored_post.insert()

        normalized_update = NormalizedSocialPost(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="instagram",
            platform_post_id=(
                stored_post.platform_post_id
            ),
            published_at=None,
            post_url=None,
            content_type="carousel",
            text="Updated normalized caption",
            hashtags=[],
            mentions=[
                "updated_account",
            ],
            tagged_accounts=[
                "model_account",
            ],
            media_urls=[
                "https://example.test/new-1.jpg",
                "https://example.test/new-2.jpg",
            ],
            language=None,
            location_name="Updated Location",
            is_pinned=True,
            metrics=NormalizedSocialMetrics(
                likes=75,
                comments=4,
                captured_at=newer_collected_at,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "instagram",
                "new_key": "new_value",
            },
        )

        changed = (
            await update_normalized_social_post_content(
                post=stored_post,
                normalized_post=normalized_update,
            )
        )

        assert changed is True

        refreshed_post = await SocialPostDocument.get(
            stored_post.id,
        )

        assert refreshed_post is not None

        # Non-empty incoming values update stored content.
        assert refreshed_post.content_type == "carousel"

        assert (
            refreshed_post.text
            == "Updated normalized caption"
        )

        assert refreshed_post.mentions == [
            "updated_account",
        ]

        assert refreshed_post.media_urls == [
            "https://example.test/new-1.jpg",
            "https://example.test/new-2.jpg",
        ]

        # Empty or None incoming content preserves stored values.
        assert refreshed_post.post_url == (
            "https://example.test/original-post"
        )

        assert refreshed_post.hashtags == [
            "Original",
            "Fashion",
        ]

        assert refreshed_post.language == "en"

        assert refreshed_post.published_at is not None

        # Existing and incoming raw fields are merged.
        assert refreshed_post.raw_data == {
            "source_platform": "instagram",
            "preserved_key": "preserved_value",
            "new_key": "new_value",
            "tagged_accounts": [
                "model_account",
            ],
            "location_name": "Updated Location",
            "is_pinned": True,
        }

        assert refreshed_post.collected_at is not None

        assert (
            ensure_utc(
                refreshed_post.collected_at
            )
            == newer_collected_at
        )

        # Content updating must not bypass metric history.
        assert refreshed_post.latest_metrics.likes == 50
        assert refreshed_post.latest_metrics.comments == 2

    finally:
        try:
            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                refreshed_post = (
                    await SocialPostDocument.get(
                        stored_post.id,
                    )
                )

                if refreshed_post is not None:
                    await refreshed_post.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_identical_or_empty_update_does_not_save():
    """
    Return False when the incoming normalized content causes no
    stored change.

    Empty optional fields and empty lists must not erase useful
    content already stored on the social post.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    collected_at = datetime(
        2026,
        7,
        15,
        9,
        0,
        tzinfo=UTC,
    )

    stored_post = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=(
                f"no-change-{uuid4().hex}"
            ),
            text="Existing content",
            content_type="unknown",
            hashtags=[
                "Existing",
            ],
            mentions=[],
            media_urls=[],
            connector_type="apify",
            raw_data={
                "source_platform": "facebook",
            },
            collected_at=collected_at,
        )

        await stored_post.insert()

        normalized_post = NormalizedSocialPost(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=(
                stored_post.platform_post_id
            ),
            published_at=None,
            post_url=None,
            content_type="unknown",
            text=None,
            hashtags=[],
            mentions=[],
            tagged_accounts=[],
            media_urls=[],
            language=None,
            location_name=None,
            is_pinned=None,
            metrics=NormalizedSocialMetrics(
                reactions=74,
                captured_at=collected_at,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "facebook",
            },
        )

        changed = (
            await update_normalized_social_post_content(
                post=stored_post,
                normalized_post=normalized_post,
            )
        )

        assert changed is False

        refreshed_post = await SocialPostDocument.get(
            stored_post.id,
        )

        assert refreshed_post is not None

        assert (
            refreshed_post.text
            == "Existing content"
        )

        assert refreshed_post.hashtags == [
            "Existing",
        ]

        assert refreshed_post.mentions == []
        assert refreshed_post.media_urls == []

        assert refreshed_post.raw_data == {
            "source_platform": "facebook",
        }

        assert refreshed_post.collected_at is not None

        assert (
            ensure_utc(
                refreshed_post.collected_at
            )
            == collected_at
        )

    finally:
        try:
            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                refreshed_post = (
                    await SocialPostDocument.get(
                        stored_post.id,
                    )
                )

                if refreshed_post is not None:
                    await refreshed_post.delete()
        finally:
            await close_mongo()
