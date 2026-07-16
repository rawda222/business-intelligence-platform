"""
Post Trend Service Tests

Verifies posts-per-week bucketing, empty-week filling, tenant
isolation, and range-boundary behavior.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.services.post_trend_service import (
    get_posts_per_week_trend,
)


async def _insert_post(
    *,
    business_id,
    social_account_id,
    platform_post_id: str,
    published_at: datetime,
) -> SocialPostDocument:
    """Persist one social post used only for trend tests."""

    post = SocialPostDocument(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="facebook",
        platform_post_id=platform_post_id,
        published_at=published_at,
        content_type="text",
        text="Post trend test",
        connector_type="apify",
        raw_data={
            "source": "post_trend_test",
        },
    )

    await post.insert()

    return post


@pytest.mark.asyncio
async def test_posts_per_week_buckets_are_business_scoped():
    """Bucket posts weekly using UTC and preserve tenant isolation."""

    business_id = uuid4()
    other_business_id = uuid4()
    social_account_id = uuid4()

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
        27,
        0,
        0,
        tzinfo=UTC,
    )

    inserted_ids: list = []

    try:
        await connect_to_mongo()

        first_post = await _insert_post(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=(
                f"trend-w1-a-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                7,
                10,
                0,
                tzinfo=UTC,
            ),
        )

        second_post = await _insert_post(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=(
                f"trend-w1-b-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                10,
                18,
                30,
                tzinfo=UTC,
            ),
        )

        # Week 2 remains empty on purpose.

        third_post = await _insert_post(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=(
                f"trend-w3-a-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                21,
                9,
                0,
                tzinfo=UTC,
            ),
        )

        outside_range_post = await _insert_post(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=(
                f"trend-out-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                8,
                3,
                12,
                0,
                tzinfo=UTC,
            ),
        )

        other_business_post = await _insert_post(
            business_id=other_business_id,
            social_account_id=social_account_id,
            platform_post_id=(
                f"trend-other-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                7,
                10,
                0,
                tzinfo=UTC,
            ),
        )

        inserted_ids = [
            first_post.id,
            second_post.id,
            third_post.id,
            outside_range_post.id,
            other_business_post.id,
        ]

        trend = await get_posts_per_week_trend(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
        )

        assert (
            trend.business_id == business_id
        )

        assert trend.range_start == range_start
        assert trend.range_end == range_end

        assert len(trend.buckets) == 3

        assert (
            trend.buckets[0].week_start
            == date(2026, 7, 6)
        )

        assert (
            trend.buckets[0].post_count == 2
        )

        assert (
            trend.buckets[1].week_start
            == date(2026, 7, 13)
        )

        assert (
            trend.buckets[1].post_count == 0
        )

        assert (
            trend.buckets[2].week_start
            == date(2026, 7, 20)
        )

        assert (
            trend.buckets[2].post_count == 1
        )

        assert trend.total_posts == 3

    finally:
        try:
            for post_id in inserted_ids:
                stored_post = (
                    await SocialPostDocument.get(
                        post_id
                    )
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_invalid_range_is_rejected():
    """Reject non-strictly-increasing ranges."""

    with pytest.raises(
        ValueError,
    ):
        await get_posts_per_week_trend(
            business_id=uuid4(),
            range_start=datetime(
                2026,
                7,
                20,
                0,
                0,
                tzinfo=UTC,
            ),
            range_end=datetime(
                2026,
                7,
                20,
                0,
                0,
                tzinfo=UTC,
            ),
        )