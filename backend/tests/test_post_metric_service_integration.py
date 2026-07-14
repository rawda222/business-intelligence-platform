"""
Post Metric Service Integration Tests

Verifies historical metric capture, duplicate suppression,
tenant isolation, post-age calculation, backfill behavior,
and latest-metrics synchronization.
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
    SocialPostMetrics,
)
from app.services.post_metric_service import (
    InvalidMetricTimestampError,
    SocialPostScopeMismatchError,
    ensure_utc,
    record_metric_snapshot,
)


@pytest.mark.asyncio
async def test_post_metric_snapshot_policy_and_tenant_isolation():
    """
    Verify metric-snapshot business rules.

    Covered behavior:
    - First snapshot is created.
    - Latest metrics are synchronized.
    - Post age is calculated.
    - Rapid identical snapshot is skipped.
    - Later identical snapshot is stored.
    - Changed metrics are stored.
    - Same timestamp is updated idempotently.
    - Historical backfill does not overwrite newer latest metrics.
    - Cross-business access is rejected.
    - Capture before publication is rejected.
    - Temporary MongoDB data is cleaned.
    """

    business_id = uuid4()
    other_business_id = uuid4()
    social_account_id = uuid4()
    collection_run_id = uuid4()

    unique_suffix = uuid4().hex

    published_at = datetime.now(UTC).replace(
        microsecond=0,
    )

    post = None

    try:
        await connect_to_mongo()

        # ====================================================
        # Create Temporary Social Post
        # ====================================================
        post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="instagram",
            platform_post_id=(
                f"metric-service-post-{unique_suffix}"
            ),
            published_at=published_at,
            text="Metric service integration test",
        )

        await post.insert()

        # ====================================================
        # First Snapshot
        # ====================================================
        first_time = published_at + timedelta(hours=1)

        first_metrics = SocialPostMetrics(
            likes=100,
            comments=10,
            shares=2,
            views=1000,
        )

        first_result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=first_metrics,
            captured_at=first_time,
            collection_run_id=collection_run_id,
        )

        assert first_result.created is True
        assert first_result.skipped is False
        assert first_result.updated_existing is False
        assert first_result.reason == "snapshot_created"

        assert (
            first_result.snapshot.post_age_seconds
            == 3600
        )

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.likes == 100
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == first_time
        )

        # ====================================================
        # Rapid Identical Snapshot Is Skipped
        # ====================================================
        rapid_time = first_time + timedelta(minutes=5)

        rapid_result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=first_metrics,
            captured_at=rapid_time,
        )

        assert rapid_result.created is False
        assert rapid_result.skipped is True

        assert (
            rapid_result.reason
            == "rapid_identical_metrics"
        )

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert snapshot_count == 1

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == rapid_time
        )

        # ====================================================
        # Later Identical Snapshot Is Preserved
        # ====================================================
        later_identical_time = (
            first_time + timedelta(hours=2)
        )

        later_identical_result = (
            await record_metric_snapshot(
                business_id=business_id,
                social_account_id=social_account_id,
                social_post_id=post.id,
                metrics=first_metrics,
                captured_at=later_identical_time,
            )
        )

        assert later_identical_result.created is True
        assert later_identical_result.skipped is False

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert snapshot_count == 2

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == later_identical_time
        )

        # ====================================================
        # Changed Metrics Are Preserved
        # ====================================================
        changed_time = (
            later_identical_time + timedelta(minutes=5)
        )

        changed_metrics = SocialPostMetrics(
            likes=180,
            comments=22,
            shares=8,
            views=2100,
        )

        changed_result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=changed_metrics,
            captured_at=changed_time,
        )

        assert changed_result.created is True
        assert changed_result.skipped is False

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert snapshot_count == 3

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.likes == 180
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == changed_time
        )

        # ====================================================
        # Same Timestamp Is Updated Idempotently
        # ====================================================
        corrected_metrics = SocialPostMetrics(
            likes=185,
            comments=23,
            shares=8,
            views=2150,
        )

        corrected_result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=corrected_metrics,
            captured_at=changed_time,
        )

        assert corrected_result.created is False
        assert corrected_result.skipped is False
        assert corrected_result.updated_existing is True

        assert (
            corrected_result.reason
            == "same_timestamp_updated"
        )

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert snapshot_count == 3

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None
        assert refreshed_post.latest_metrics.likes == 185
        assert refreshed_post.latest_metrics.comments == 23
        assert refreshed_post.latest_metrics.views == 2150
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == changed_time
        )

        # ====================================================
        # Historical Backfill Must Not Replace Latest Metrics
        # ====================================================
        backfill_time = (
            published_at + timedelta(minutes=30)
        )

        backfill_metrics = SocialPostMetrics(
            likes=50,
            comments=3,
            shares=0,
            views=400,
        )

        backfill_result = await record_metric_snapshot(
            business_id=business_id,
            social_account_id=social_account_id,
            social_post_id=post.id,
            metrics=backfill_metrics,
            captured_at=backfill_time,
        )

        assert backfill_result.created is True
        assert backfill_result.skipped is False

        snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert snapshot_count == 4

        refreshed_post = await SocialPostDocument.get(
            post.id
        )

        assert refreshed_post is not None

        # The newest observation must remain the latest metrics.
        assert refreshed_post.latest_metrics.likes == 185
        assert refreshed_post.latest_metrics.comments == 23
        assert refreshed_post.latest_metrics.views == 2150
        assert refreshed_post.latest_metrics.captured_at is not None

        assert (
            ensure_utc(
                refreshed_post.latest_metrics.captured_at
            )
            == changed_time
        )

        # Verify that the historical backfill still exists.
        stored_backfill = await (
            PostMetricSnapshotDocument.find_one(
                PostMetricSnapshotDocument.social_post_id
                == post.id,
                PostMetricSnapshotDocument.captured_at
                == backfill_time.replace(tzinfo=None),
            )
        )

        assert stored_backfill is not None
        assert stored_backfill.metrics.likes == 50

        assert (
            stored_backfill.post_age_seconds
            == 1800
        )

        # ====================================================
        # Cross-Business Access Is Rejected
        # ====================================================
        with pytest.raises(
            SocialPostScopeMismatchError
        ):
            await record_metric_snapshot(
                business_id=other_business_id,
                social_account_id=social_account_id,
                social_post_id=post.id,
                metrics=changed_metrics,
                captured_at=(
                    changed_time + timedelta(hours=1)
                ),
            )

        # ====================================================
        # Capture Before Publication Is Rejected
        # ====================================================
        with pytest.raises(
            InvalidMetricTimestampError
        ):
            await record_metric_snapshot(
                business_id=business_id,
                social_account_id=social_account_id,
                social_post_id=post.id,
                metrics=changed_metrics,
                captured_at=(
                    published_at - timedelta(seconds=1)
                ),
            )

        # No invalid snapshot should have been inserted.
        final_snapshot_count = await (
            PostMetricSnapshotDocument.find(
                PostMetricSnapshotDocument.social_post_id
                == post.id
            ).count()
        )

        assert final_snapshot_count == 4

    finally:
        try:
            if post is not None and post.id is not None:
                await PostMetricSnapshotDocument.find(
                    PostMetricSnapshotDocument.social_post_id
                    == post.id
                ).delete()

                stored_post = await SocialPostDocument.get(
                    post.id
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()