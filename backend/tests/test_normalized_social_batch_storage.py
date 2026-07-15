"""
Normalized Social Batch Storage Tests

Verifies storing multiple normalized posts in one collection run
while preserving platform-specific metrics and summary counts.
"""

from datetime import UTC, datetime
from uuid import uuid4
from types import SimpleNamespace

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
    store_normalized_social_posts,
)
from app.services import (
    normalized_social_storage_service,
)


@pytest.mark.asyncio
async def test_batch_stores_facebook_and_instagram_posts():
    """
    Store Facebook and Instagram posts in one normalized batch.

    Facebook reactions remain reactions.
    Instagram likes remain likes.
    """

    business_id = uuid4()

    facebook_account_id = uuid4()
    instagram_account_id = uuid4()

    collection_run_id = uuid4()

    unique_suffix = uuid4().hex

    captured_at = datetime(
        2026,
        7,
        15,
        12,
        0,
        tzinfo=UTC,
    )

    stored_post_ids = []

    try:
        await connect_to_mongo()

        posts = [
            NormalizedSocialPost(
                business_id=business_id,
                social_account_id=facebook_account_id,
                platform="facebook",
                platform_post_id=(
                    f"FacebookBatch{unique_suffix}"
                ),
                published_at=datetime(
                    2026,
                    7,
                    14,
                    9,
                    0,
                    tzinfo=UTC,
                ),
                content_type="text",
                text="Facebook batch post",
                metrics=NormalizedSocialMetrics(
                    likes=None,
                    reactions=74,
                    comments=8,
                    shares=5,
                    views=0,
                    captured_at=captured_at,
                ),
                connector_type="apify",
                raw_data={
                    "source_platform": "facebook",
                },
            ),
            NormalizedSocialPost(
                business_id=business_id,
                social_account_id=instagram_account_id,
                platform="instagram",
                platform_post_id=(
                    f"InstagramBatch{unique_suffix}"
                ),
                published_at=datetime(
                    2026,
                    7,
                    14,
                    10,
                    0,
                    tzinfo=UTC,
                ),
                content_type="carousel",
                text="Instagram batch post",
                metrics=NormalizedSocialMetrics(
                    likes=105,
                    reactions=None,
                    comments=4,
                    captured_at=captured_at,
                ),
                connector_type="apify",
                raw_data={
                    "source_platform": "instagram",
                },
            ),
        ]

        result = await store_normalized_social_posts(
            posts,
            collection_run_id=collection_run_id,
        )

        stored_post_ids = [
            item.post.id
            for item in result.results
            if item.post.id is not None
        ]

        assert result.posts_received == 2
        assert result.posts_succeeded == 2
        assert result.posts_created == 2
        assert result.posts_updated == 0

        assert result.snapshots_created == 2
        assert result.snapshots_skipped == 0

        assert (
            result.snapshots_updated_existing
            == 0
        )

        assert result.failures == []
        assert len(result.results) == 2

        facebook_result = result.results[0]
        instagram_result = result.results[1]

        assert (
            facebook_result.post.platform
            == "facebook"
        )

        assert (
            facebook_result.post.latest_metrics.likes
            is None
        )

        assert (
            facebook_result.post.latest_metrics.reactions
            == 74
        )

        assert (
            instagram_result.post.platform
            == "instagram"
        )

        assert (
            instagram_result.post.latest_metrics.likes
            == 105
        )

        assert (
            instagram_result.post.latest_metrics.reactions
            is None
        )

    finally:
        try:
            for post_id in stored_post_ids:
                await PostMetricSnapshotDocument.find(
                    PostMetricSnapshotDocument.social_post_id
                    == post_id
                ).delete()

                post = await SocialPostDocument.get(
                    post_id,
                )

                if post is not None:
                    await post.delete()
        finally:
            await close_mongo()


def build_batch_test_post(
    *,
    platform_post_id: str,
) -> NormalizedSocialPost:
    """
    Build one valid normalized post for batch-policy tests.
    """

    return NormalizedSocialPost(
        business_id=uuid4(),
        social_account_id=uuid4(),
        platform="facebook",
        platform_post_id=platform_post_id,
        published_at=datetime(
            2026,
            7,
            14,
            9,
            0,
            tzinfo=UTC,
        ),
        content_type="text",
        text="Batch error-policy test",
        metrics=NormalizedSocialMetrics(
            reactions=74,
            comments=8,
            captured_at=datetime(
                2026,
                7,
                15,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        connector_type="apify",
        raw_data={
            "source_platform": "facebook",
        },
    )

@pytest.mark.asyncio
async def test_batch_continues_after_one_post_failure(
    monkeypatch,
):
    """
    Record one failure and continue processing later posts.

    The batch diagnostic must contain only minimal traceability
    fields rather than the complete normalized payload.
    """

    successful_post = build_batch_test_post(
        platform_post_id="SuccessfulBatchPost",
    )

    failed_post = build_batch_test_post(
        platform_post_id="FailedBatchPost",
    )

    later_successful_post = build_batch_test_post(
        platform_post_id="LaterSuccessfulBatchPost",
    )

    processed_post_ids: list[str] = []

    async def fake_store_normalized_social_post(
        normalized_post,
        *,
        collection_run_id=None,
    ):
        del collection_run_id

        processed_post_ids.append(
            normalized_post.platform_post_id
        )

        if (
            normalized_post.platform_post_id
            == "FailedBatchPost"
        ):
            raise RuntimeError(
                "Simulated storage failure"
            )

        return SimpleNamespace(
            post=SimpleNamespace(
                platform_post_id=(
                    normalized_post.platform_post_id
                ),
            ),
            snapshot=SimpleNamespace(
                created=True,
                skipped=False,
                updated_existing=False,
            ),
            post_created=True,
            post_updated=False,
        )

    monkeypatch.setattr(
        normalized_social_storage_service,
        "store_normalized_social_post",
        fake_store_normalized_social_post,
    )

    result = await store_normalized_social_posts(
        [
            successful_post,
            failed_post,
            later_successful_post,
        ],
        collection_run_id=uuid4(),
        continue_on_error=True,
    )

    assert processed_post_ids == [
        "SuccessfulBatchPost",
        "FailedBatchPost",
        "LaterSuccessfulBatchPost",
    ]

    assert result.posts_received == 3
    assert result.posts_succeeded == 2
    assert result.posts_created == 2
    assert result.posts_updated == 0

    assert result.snapshots_created == 2
    assert result.snapshots_skipped == 0

    assert (
        result.snapshots_updated_existing
        == 0
    )

    assert len(result.results) == 2
    assert len(result.failures) == 1

    assert result.failures[0] == {
        "platform": "facebook",
        "platform_post_id": "FailedBatchPost",
        "error_type": "RuntimeError",
        "error_message": (
            "Simulated storage failure"
        ),
    }

    failure_text = str(
        result.failures[0]
    )

    assert "Batch error-policy test" not in failure_text
    assert "raw_data" not in failure_text

@pytest.mark.asyncio
async def test_batch_strict_mode_raises_first_failure(
    monkeypatch,
):
    """
    Re-raise the first storage exception when error continuation
    is disabled.
    """

    first_post = build_batch_test_post(
        platform_post_id="FirstStrictPost",
    )

    failed_post = build_batch_test_post(
        platform_post_id="FailedStrictPost",
    )

    never_processed_post = build_batch_test_post(
        platform_post_id="NeverProcessedPost",
    )

    processed_post_ids: list[str] = []

    async def fake_store_normalized_social_post(
        normalized_post,
        *,
        collection_run_id=None,
    ):
        del collection_run_id

        processed_post_ids.append(
            normalized_post.platform_post_id
        )

        if (
            normalized_post.platform_post_id
            == "FailedStrictPost"
        ):
            raise RuntimeError(
                "Strict batch failure"
            )

        return SimpleNamespace(
            post=SimpleNamespace(
                platform_post_id=(
                    normalized_post.platform_post_id
                ),
            ),
            snapshot=SimpleNamespace(
                created=True,
                skipped=False,
                updated_existing=False,
            ),
            post_created=True,
            post_updated=False,
        )

    monkeypatch.setattr(
        normalized_social_storage_service,
        "store_normalized_social_post",
        fake_store_normalized_social_post,
    )

    with pytest.raises(
        RuntimeError,
        match="Strict batch failure",
    ):
        await store_normalized_social_posts(
            [
                first_post,
                failed_post,
                never_processed_post,
            ],
            collection_run_id=uuid4(),
            continue_on_error=False,
        )

    assert processed_post_ids == [
        "FirstStrictPost",
        "FailedStrictPost",
    ]

    assert (
        "NeverProcessedPost"
        not in processed_post_ids
    )