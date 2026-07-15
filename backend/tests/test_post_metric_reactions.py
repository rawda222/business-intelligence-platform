"""
Post Metric Reactions Tests

Verifies that Facebook reactions remain separate from likes,
participate in metric comparison, and persist through MongoDB
snapshot and latest-metrics storage.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)
from app.services.post_metric_service import (
    metrics_are_equal,
    record_metric_snapshot,
)


def test_social_post_metrics_support_reactions():
    """Accept non-negative reactions and keep them separate."""

    metrics = SocialPostMetrics(
        likes=None,
        reactions=74,
        comments=8,
        shares=5,
        views=0,
    )

    assert metrics.likes is None
    assert metrics.reactions == 74
    assert metrics.views == 0

    with pytest.raises(ValidationError):
        SocialPostMetrics(
            reactions=-1,
        )


def test_metric_comparison_detects_reactions_change():
    """A reactions-only change must be a real metric change."""

    first = SocialPostMetrics(
        reactions=74,
        comments=8,
        shares=5,
        views=0,
    )

    identical = SocialPostMetrics(
        reactions=74,
        comments=8,
        shares=5,
        views=0,
    )

    changed = SocialPostMetrics(
        reactions=75,
        comments=8,
        shares=5,
        views=0,
    )

    assert metrics_are_equal(
        first,
        identical,
    ) is True

    assert metrics_are_equal(
        first,
        changed,
    ) is False


@pytest.mark.asyncio
async def test_reactions_persist_in_snapshot_and_latest_metrics():
    """
    Persist reactions in both the historical snapshot and the
    social post's latest metrics.
    """

    business_id = uuid4()
    social_account_id = uuid4()
    unique_suffix = uuid4().hex

    published_at = datetime.now(UTC).replace(
        microsecond=0,
    )

    captured_at = (
        published_at + timedelta(hours=1)
    )

    post = None

    try:
        await connect_to_mongo()

        post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=(
                f"reactions-test-{unique_suffix}"
            ),
            published_at=published_at,
            text="Facebook reactions persistence test",
        )

        await post.insert()

        result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=74,
                comments=8,
                shares=5,
                views=0,
            ),
            captured_at=captured_at,
        )
        assert result.created is True
        assert result.skipped is False
        assert result.updated_existing is False
        assert result.reason == "snapshot_created"

        assert result.snapshot.metrics.likes is None

        assert (
            result.snapshot.metrics.reactions
            == 74
        )

        assert (
            result.snapshot.metrics.comments
            == 8
        )

        assert (
            result.snapshot.metrics.shares
            == 5
        )

        assert (
            result.snapshot.metrics.views
            == 0
        )

        refreshed_post = await SocialPostDocument.get(
            post.id,
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.likes is None

        assert (
            refreshed_post.latest_metrics.reactions
            == 74
        )

        assert (
            refreshed_post.latest_metrics.comments
            == 8
        )

        assert (
            refreshed_post.latest_metrics.shares
            == 5
        )

        assert (
            refreshed_post.latest_metrics.views
            == 0
        )

    finally:
        try:
            if post is not None and post.id is not None:
                await PostMetricSnapshotDocument.find(
                    PostMetricSnapshotDocument.social_post_id
                    == post.id
                ).delete()

                stored_post = await SocialPostDocument.get(
                    post.id,
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()
