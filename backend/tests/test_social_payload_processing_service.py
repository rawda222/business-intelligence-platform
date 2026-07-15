"""
Social Payload Processing Service Tests

Verifies the complete raw social payload workflow:

- Normalize Facebook and Instagram collector payloads.
- Store normalized posts through batch storage.
- Preserve platform-specific metric semantics.
- Return normalized comments without claiming persistence.
- Handle payloads without a valid posts list safely.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.services.social_payload_processing_service import (
    process_facebook_payload,
    process_instagram_payload,
)
from tests.test_facebook_normalizer import (
    build_facebook_payload,
)
from tests.test_instagram_normalizer import (
    build_instagram_payload,
)
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)


async def delete_processing_test_posts(
    post_ids,
) -> None:
    """Clean comments, snapshots, and posts."""

    for post_id in post_ids:
        await SocialCommentDocument.find(
            SocialCommentDocument.social_post_id
            == post_id
        ).delete()

        await PostMetricSnapshotDocument.find(
            PostMetricSnapshotDocument.social_post_id
            == post_id
        ).delete()

        stored_post = await SocialPostDocument.get(
            post_id
        )

        if stored_post is not None:
            await stored_post.delete()


@pytest.mark.asyncio
async def test_facebook_raw_payload_is_normalized_and_stored():
    """
    Process one real-shaped or Facebook-style fixture payload.

    The normalized post is persisted with Facebook reactions,
    while normalized comments are returned but not persisted.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    collection_run_id = uuid4()

    stored_post_ids = []

    try:
        await connect_to_mongo()

        result = await process_facebook_payload(
            build_facebook_payload(),
            business_id=business_id,
            social_account_id=social_account_id,
            connector_type="apify",
            collection_run_id=collection_run_id,
        )

        stored_post_ids = [
            item.post.id
            for item in result.storage.results
            if item.post.id is not None
        ]

        assert result.platform == "facebook"

        assert result.posts_normalized == 1
        assert result.comments_normalized == 2

        # Comment persistence has not been introduced yet.
        assert result.comments_persisted == 2

        assert (
            result.comment_storage.comments_received
            == 2
        )

        assert (
            result.comment_storage.comments_succeeded
            == 2
        )

        assert (
            result.comment_storage.comments_created
            + result.comment_storage.comments_unchanged
            == 2
        )

        assert result.comment_storage.failures == []

        assert result.storage.posts_received == 1
        assert result.storage.posts_succeeded == 1
        assert result.storage.posts_created == 1
        assert result.storage.posts_updated == 0

        assert result.storage.snapshots_created == 1
        assert result.storage.snapshots_skipped == 0

        assert (
            result.storage.snapshots_updated_existing
            == 0
        )

        assert result.storage.failures == []
        assert len(result.storage.results) == 1

        normalized_post = result.normalized_posts[0]

        assert normalized_post.business_id == business_id

        assert (
            normalized_post.social_account_id
            == social_account_id
        )

        assert normalized_post.platform == "facebook"

        assert (
            normalized_post.platform_post_id
            == "1457988579706770"
        )

        assert normalized_post.metrics.likes is None

        assert (
            normalized_post.metrics.reactions
            == 74
        )

        assert normalized_post.metrics.comments == 8
        assert normalized_post.metrics.shares == 5

        # An observed zero must remain zero.
        assert normalized_post.metrics.views == 0

        stored_result = result.storage.results[0]

        assert stored_result.post_created is True
        assert stored_result.post_updated is False

        assert (
            stored_result.post.business_id
            == business_id
        )

        assert (
            stored_result.post.social_account_id
            == social_account_id
        )

        assert (
            stored_result.post.latest_metrics.likes
            is None
        )

        assert (
            stored_result.post.latest_metrics.reactions
            == 74
        )

        assert (
            stored_result.post.latest_metrics.comments
            == 8
        )

        assert (
            stored_result.post.latest_metrics.shares
            == 5
        )

        assert (
            stored_result.post.latest_metrics.views
            == 0
        )

        assert stored_result.snapshot.created is True
        assert stored_result.snapshot.skipped is False

        assert (
            stored_result.snapshot.reason
            == "snapshot_created"
        )

        assert len(result.normalized_comments) == 2

        for comment in result.normalized_comments:
            assert comment.business_id == business_id

            assert (
                comment.social_account_id
                == social_account_id
            )

            assert comment.platform == "facebook"

            assert (
                comment.platform_post_id
                == "1457988579706770"
            )

    finally:
        try:
            await delete_processing_test_posts(
                stored_post_ids
            )
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_instagram_raw_payload_is_normalized_and_stored():
    """
    Process one real Instagram-style fixture payload.

    Both normalized posts are persisted with Instagram likes kept
    separate from Facebook reactions.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    collection_run_id = uuid4()

    explicit_collected_at = datetime(
        2026,
        7,
        15,
        18,
        0,
        tzinfo=UTC,
    )

    stored_post_ids = []

    try:
        await connect_to_mongo()

        result = await process_instagram_payload(
            build_instagram_payload(),
            business_id=business_id,
            social_account_id=social_account_id,
            connector_type="apify",
            collected_at=explicit_collected_at,
            collection_run_id=collection_run_id,
        )

        stored_post_ids = [
            item.post.id
            for item in result.storage.results
            if item.post.id is not None
        ]

        assert result.platform == "instagram"

        assert result.posts_normalized == 2
        assert result.comments_normalized == 2
        assert result.comments_persisted == 2

        assert (
            result.comment_storage.comments_received
            == 2
        )

        assert (
            result.comment_storage.comments_succeeded
            == 2
        )

        assert (
            result.comment_storage.comments_created
            + result.comment_storage.comments_unchanged
            == 2
        )

        assert result.comment_storage.failures == []

        assert result.storage.posts_received == 2
        assert result.storage.posts_succeeded == 2
        assert result.storage.posts_created == 2
        assert result.storage.posts_updated == 0

        assert result.storage.snapshots_created == 2
        assert result.storage.snapshots_skipped == 0

        assert (
            result.storage.snapshots_updated_existing
            == 0
        )

        assert result.storage.failures == []
        assert len(result.storage.results) == 2

        carousel_post = result.normalized_posts[0]
        image_post = result.normalized_posts[1]

        assert carousel_post.platform == "instagram"

        assert (
            carousel_post.platform_post_id
            == "DZuTXx3jBxd"
        )

        assert carousel_post.metrics.likes == 105

        assert (
            carousel_post.metrics.reactions
            is None
        )

        assert (
            carousel_post.metrics.captured_at
            == explicit_collected_at
        )

        assert image_post.platform == "instagram"

        assert (
            image_post.platform_post_id
            == "ImagePostABC"
        )

        assert image_post.metrics.likes == 0
        assert image_post.metrics.comments == 0

        assert (
            image_post.metrics.reactions
            is None
        )

        assert len(stored_post_ids) == 2

        stored_by_platform_id = {
            item.post.platform_post_id: item.post
            for item in result.storage.results
        }

        stored_carousel = stored_by_platform_id[
            "DZuTXx3jBxd"
        ]

        stored_image = stored_by_platform_id[
            "ImagePostABC"
        ]

        assert stored_carousel.latest_metrics.likes == 105

        assert (
            stored_carousel.latest_metrics.reactions
            is None
        )

        assert stored_image.latest_metrics.likes == 0

        assert (
            stored_image.latest_metrics.comments
            == 0
        )

        assert (
            stored_image.latest_metrics.reactions
            is None
        )

        for comment in result.normalized_comments:
            assert comment.business_id == business_id

            assert (
                comment.social_account_id
                == social_account_id
            )

            assert comment.platform == "instagram"

    finally:
        try:
            await delete_processing_test_posts(
                stored_post_ids
            )
        finally:
            await close_mongo()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "processor_name",
        "payload",
    ),
    [
        (
            "facebook",
            {
                "source": {
                    "collected_at": (
                        "2026-07-15T18:00:00Z"
                    ),
                },
                "posts": "not-a-list",
            },
        ),
        (
            "instagram",
            {
                "profile": {
                    "scraped_at": (
                        "2026-07-15T18:00:00Z"
                    ),
                },
                "posts": None,
            },
        ),
    ],
)
async def test_payload_without_valid_posts_returns_empty_result(
    processor_name,
    payload,
):
    """
    Return an empty successful result when posts is not a list.

    This follows the existing platform normalizer behavior.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    if processor_name == "facebook":
        result = await process_facebook_payload(
            payload,
            business_id=business_id,
            social_account_id=social_account_id,
        )
    else:
        result = await process_instagram_payload(
            payload,
            business_id=business_id,
            social_account_id=social_account_id,
        )

    assert result.platform == processor_name

    assert result.posts_normalized == 0
    assert result.comments_normalized == 0
    assert result.comments_persisted == 0
    assert (
        result.comment_storage.comments_received
        == 0
    )

    assert (
        result.comment_storage.comments_succeeded
        == 0
    )

    assert result.comment_storage.failures == []
    assert result.comment_storage.results == []

    assert result.storage.posts_received == 0
    assert result.storage.posts_succeeded == 0
    assert result.storage.posts_created == 0
    assert result.storage.posts_updated == 0

    assert result.storage.snapshots_created == 0
    assert result.storage.snapshots_skipped == 0

    assert (
        result.storage.snapshots_updated_existing
        == 0
    )

    assert result.storage.failures == []
    assert result.storage.results == []