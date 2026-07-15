"""
Normalized Social Storage Workflow Tests

Verifies the complete normalized-post persistence workflow:

- Create a social post.
- Record its first metric snapshot.
- Update the same post without creating a duplicate.
- Record changed Facebook reactions.
- Skip a rapid identical metric observation.
- Preserve tenant-scoped storage behavior.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)
from app.services.normalized_social_storage_service import (
    store_normalized_social_post,
)
from app.services.post_metric_service import (
    ensure_utc,
)


@pytest.mark.asyncio
async def test_facebook_normalized_storage_workflow():
    """
    Store repeated normalized Facebook observations safely.

    First observation:
        Creates one post and one metric snapshot.

    Second observation:
        Updates the same post, preserves one MongoDB post, and
        records changed reactions as a second snapshot.

    Third rapid identical observation:
        Keeps the same post and skips an unnecessary snapshot.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    collection_run_id = uuid4()

    unique_suffix = uuid4().hex

    platform_post_id = (
        f"FacebookWorkflow{unique_suffix}"
    )

    published_at = datetime(
        2026,
        7,
        14,
        8,
        0,
        tzinfo=UTC,
    )

    first_capture = datetime(
        2026,
        7,
        15,
        9,
        0,
        tzinfo=UTC,
    )

    second_capture = (
        first_capture + timedelta(hours=1)
    )

    rapid_capture = (
        second_capture + timedelta(minutes=5)
    )

    stored_post_id = None

    try:
        await connect_to_mongo()

        # ====================================================
        # First Collection: Create Post and Snapshot
        # ====================================================
        first_normalized_post = NormalizedSocialPost(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=published_at,
            post_url=(
                "https://example.test/facebook-post"
            ),
            content_type="text",
            text="Original Facebook post text",
            hashtags=[
                "Business",
            ],
            mentions=[],
            tagged_accounts=[],
            media_urls=[],
            language="en",
            location_name=None,
            is_pinned=False,
            metrics=NormalizedSocialMetrics(
                likes=None,
                reactions=74,
                comments=8,
                shares=5,
                views=0,
                captured_at=first_capture,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "facebook",
                "source_post_id": platform_post_id,
            },
        )

        first_result = await store_normalized_social_post(
            first_normalized_post,
            collection_run_id=collection_run_id,
        )

        stored_post_id = first_result.post.id

        assert stored_post_id is not None
        assert first_result.post_created is True
        assert first_result.post_updated is False

        assert first_result.snapshot.created is True
        assert first_result.snapshot.skipped is False

        assert (
            first_result.snapshot.reason
            == "snapshot_created"
        )

        assert first_result.post.latest_metrics.likes is None

        assert (
            first_result.post.latest_metrics.reactions
            == 74
        )

        assert (
            first_result.post.latest_metrics.comments
            == 8
        )

        assert first_result.post.latest_metrics.views == 0

        post_count = await (
            SocialPostDocument.find(
                SocialPostDocument.business_id
                == business_id,
                SocialPostDocument.social_account_id
                == social_account_id,
                SocialPostDocument.platform
                == "facebook",
                SocialPostDocument.platform_post_id
                == platform_post_id,
            ).count()
        )

        assert post_count == 1

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == stored_post_id
            ).count()
        )

        assert snapshot_count == 1

        # ====================================================
        # Second Collection: Update Same Post
        # ====================================================
        second_normalized_post = NormalizedSocialPost(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=published_at,
            post_url=(
                "https://example.test/facebook-post"
            ),
            content_type="text",
            text="Updated Facebook post text",
            hashtags=[
                "Business",
                "Update",
            ],
            mentions=[
                "example_account",
            ],
            tagged_accounts=[],
            media_urls=[],
            language="en",
            location_name=None,
            is_pinned=True,
            metrics=NormalizedSocialMetrics(
                likes=None,
                reactions=95,
                comments=11,
                shares=7,
                views=0,
                captured_at=second_capture,
            ),
            connector_type="apify",
            raw_data={
                "source_platform": "facebook",
                "source_post_id": platform_post_id,
                "second_collection": True,
            },
        )

        second_result = await store_normalized_social_post(
            second_normalized_post,
            collection_run_id=collection_run_id,
        )

        assert second_result.post.id == stored_post_id
        assert second_result.post_created is False
        assert second_result.post_updated is True

        assert second_result.snapshot.created is True
        assert second_result.snapshot.skipped is False

        assert (
            second_result.post.text
            == "Updated Facebook post text"
        )

        assert second_result.post.hashtags == [
            "Business",
            "Update",
        ]

        assert second_result.post.mentions == [
            "example_account",
        ]

        assert (
            second_result.post.raw_data[
                "second_collection"
            ]
            is True
        )

        assert second_result.post.latest_metrics.likes is None

        assert (
            second_result.post.latest_metrics.reactions
            == 95
        )

        assert (
            second_result.post.latest_metrics.comments
            == 11
        )

        assert (
            second_result.post.latest_metrics.shares
            == 7
        )

        post_count = await (
            SocialPostDocument.find(
                SocialPostDocument.business_id
                == business_id,
                SocialPostDocument.social_account_id
                == social_account_id,
                SocialPostDocument.platform
                == "facebook",
                SocialPostDocument.platform_post_id
                == platform_post_id,
            ).count()
        )

        # Updating must not create a duplicate post.
        assert post_count == 1

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == stored_post_id
            ).count()
        )

        assert snapshot_count == 2

        # ====================================================
        # Third Collection: Rapid Identical Metrics
        # ====================================================
        rapid_normalized_post = (
            second_normalized_post.model_copy(
                update={
                    "metrics": NormalizedSocialMetrics(
                        likes=None,
                        reactions=95,
                        comments=11,
                        shares=7,
                        views=0,
                        captured_at=rapid_capture,
                    ),
                },
            )
        )

        rapid_result = await store_normalized_social_post(
            rapid_normalized_post,
            collection_run_id=collection_run_id,
        )

        assert rapid_result.post.id == stored_post_id
        assert rapid_result.post_created is False
        assert rapid_result.post_updated is True

        assert rapid_result.snapshot.created is False
        assert rapid_result.snapshot.skipped is True

        assert (
            rapid_result.snapshot.reason
            == "rapid_identical_metrics"
        )

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == stored_post_id
            ).count()
        )

        # Rapid identical metrics must not create snapshot 3.
        assert snapshot_count == 2

        refreshed_post = await SocialPostDocument.get(
            stored_post_id,
        )

        assert refreshed_post is not None

        assert (
            refreshed_post.latest_metrics.reactions
            == 95
        )

        assert (
            refreshed_post.latest_metrics.captured_at
            is not None
        )

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == rapid_capture
        )

    finally:
        try:
            if stored_post_id is not None:
                await PostMetricSnapshotDocument.find(
                    PostMetricSnapshotDocument.social_post_id
                    == stored_post_id
                ).delete()

                stored_post = await SocialPostDocument.get(
                    stored_post_id,
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()