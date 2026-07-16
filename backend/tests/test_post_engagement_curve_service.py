"""
Post Engagement Curve Service Tests

Verifies per-day latest-snapshot bucketing, tenant isolation, range
handling, and error behavior for the post engagement curve query.
"""

from datetime import UTC, date, datetime, timedelta
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
from app.services.post_engagement_curve_service import (
    PostEngagementCurvePostNotFoundError,
    get_post_engagement_curve,
)
from app.services.post_metric_service import (
    record_metric_snapshot,
)


async def _insert_test_post(
    *,
    business_id,
    social_account_id,
    platform_post_id: str,
    published_at: datetime,
) -> SocialPostDocument:
    """Persist one social post used only for engagement-curve tests."""

    post = SocialPostDocument(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="facebook",
        platform_post_id=platform_post_id,
        published_at=published_at,
        content_type="text",
        text="Engagement curve test",
        connector_type="apify",
        raw_data={
            "source": (
                "engagement_curve_test"
            ),
        },
    )

    await post.insert()

    return post


@pytest.mark.asyncio
async def test_post_engagement_curve_uses_latest_per_day():
    """Bucket snapshots by UTC date and expose the latest per day."""

    business_id = uuid4()
    social_account_id = uuid4()

    published_at = datetime(
        2026,
        7,
        6,
        9,
        0,
        tzinfo=UTC,
    )

    range_start = datetime(
        2026,
        7,
        6,
        0,
        0,
        tzinfo=UTC,
    )

    range_end = datetime(
        2026,
        7,
        11,
        0,
        0,
        tzinfo=UTC,
    )

    post = None

    try:
        await connect_to_mongo()

        post = await _insert_test_post(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            platform_post_id=(
                f"engagement-curve-"
                f"{uuid4().hex}"
            ),
            published_at=published_at,
        )

        # ========================================
        # Day 1: two captures
        # ========================================
        day_one_first_captured_at = (
            published_at + timedelta(hours=2)
        )

        day_one_second_captured_at = (
            published_at + timedelta(hours=8)
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=post.id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=10,
                comments=1,
                shares=0,
                views=50,
            ),
            captured_at=(
                day_one_first_captured_at
            ),
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=post.id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=25,
                comments=3,
                shares=1,
                views=120,
            ),
            captured_at=(
                day_one_second_captured_at
            ),
        )

        # ========================================
        # Day 2: single capture
        # ========================================
        day_two_captured_at = datetime(
            2026,
            7,
            8,
            10,
            0,
            tzinfo=UTC,
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=post.id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=60,
                comments=6,
                shares=2,
                views=300,
            ),
            captured_at=day_two_captured_at,
        )

        # ========================================
        # Snapshot outside range should be ignored
        # ========================================
        outside_range_captured_at = datetime(
            2026,
            7,
            15,
            10,
            0,
            tzinfo=UTC,
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=post.id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=999,
                comments=99,
                shares=99,
                views=9999,
            ),
            captured_at=(
                outside_range_captured_at
            ),
        )

        curve = await get_post_engagement_curve(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=post.id,
            range_start=range_start,
            range_end=range_end,
        )

        assert (
            curve.business_id == business_id
        )

        assert (
            curve.social_account_id
            == social_account_id
        )

        assert (
            curve.social_post_id == post.id
        )

        assert (
            curve.range_start == range_start
        )

        assert curve.range_end == range_end

        assert len(curve.points) == 2

        first_point = curve.points[0]

        assert (
            first_point.day
            == date(2026, 7, 6)
        )

        assert (
            first_point.captured_at
            == day_one_second_captured_at
        )

        assert first_point.reactions == 25
        assert first_point.comments == 3
        assert first_point.shares == 1
        assert first_point.views == 120
        assert first_point.likes is None

        second_point = curve.points[1]

        assert (
            second_point.day
            == date(2026, 7, 8)
        )

        assert (
            second_point.captured_at
            == day_two_captured_at
        )

        assert second_point.reactions == 60
        assert second_point.comments == 6
        assert second_point.shares == 2
        assert second_point.views == 300
        assert second_point.likes is None

    finally:
        try:
            if (
                post is not None
                and post.id is not None
            ):
                await (
                    PostMetricSnapshotDocument
                    .find(
                        PostMetricSnapshotDocument
                        .social_post_id
                        == post.id
                    )
                    .delete()
                )

                stored_post = (
                    await SocialPostDocument.get(
                        post.id
                    )
                )

                if stored_post is not None:
                    await (
                        stored_post.delete()
                    )
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_engagement_curve_rejects_missing_post():
    """Raise a specific error when the post is not in tenant scope."""

    try:
        await connect_to_mongo()

        # An id that does not exist in the collection.
        from bson import ObjectId

        random_post_id = ObjectId()

        with pytest.raises(
            PostEngagementCurvePostNotFoundError,
        ):
            await get_post_engagement_curve(
                business_id=uuid4(),
                social_account_id=uuid4(),
                social_post_id=random_post_id,
                range_start=datetime(
                    2026,
                    7,
                    6,
                    0,
                    0,
                    tzinfo=UTC,
                ),
                range_end=datetime(
                    2026,
                    7,
                    11,
                    0,
                    0,
                    tzinfo=UTC,
                ),
            )

    finally:
        await close_mongo()


@pytest.mark.asyncio
async def test_engagement_curve_rejects_invalid_range():
    """Reject a range whose end does not follow its start."""

    with pytest.raises(
        ValueError,
    ):
        await get_post_engagement_curve(
            business_id=uuid4(),
            social_account_id=uuid4(),
            social_post_id=uuid4(),
            range_start=datetime(
                2026,
                7,
                6,
                0,
                0,
                tzinfo=UTC,
            ),
            range_end=datetime(
                2026,
                7,
                6,
                0,
                0,
                tzinfo=UTC,
            ),
        )