"""
Review Trend Service Tests

Verifies monthly bucketing, tenant scope, rating averaging, and
range boundary handling for the reviews-per-month trend.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.services.review_trend_service import (
    get_reviews_per_month_trend,
)


async def _insert_review(
    *,
    business_id,
    published_at: datetime,
    rating: float | None,
    is_meaningful: bool,
    source: str = "google_maps",
) -> CustomerReviewDocument:
    """Persist one customer review for review-trend tests."""

    review = CustomerReviewDocument(
        business_id=business_id,
        source=source,
        source_review_id=(
            f"review-{uuid4().hex}"
        ),
        deduplication_key=(
            f"id:review-{uuid4().hex}"
        ),
        text="Review trend test",
        language="ar",
        rating=rating,
        published_at=published_at,
        collected_at=published_at,
        information_quality=(
            "high"
            if is_meaningful
            else "low"
        ),
        is_meaningful=is_meaningful,
        is_emoji_only=False,
        raw_data={
            "source": "review_trend_test",
        },
    )

    await review.insert()

    return review


@pytest.mark.asyncio
async def test_reviews_per_month_trend_is_business_scoped():
    """
    Bucket reviews monthly and compute per-month rating averages.
    """

    business_id = uuid4()
    other_business_id = uuid4()

    range_start = datetime(
        2026,
        6,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    range_end = datetime(
        2026,
        9,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    inserted_ids = []

    try:
        await connect_to_mongo()

        # ========================================
        # June: two reviews, both meaningful
        # ========================================
        june_first = await _insert_review(
            business_id=business_id,
            published_at=datetime(
                2026,
                6,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            rating=5.0,
            is_meaningful=True,
        )

        june_second = await _insert_review(
            business_id=business_id,
            published_at=datetime(
                2026,
                6,
                20,
                12,
                0,
                tzinfo=UTC,
            ),
            rating=3.0,
            is_meaningful=True,
        )

        # ========================================
        # July: one meaningful, one no-rating
        # ========================================
        july_first = await _insert_review(
            business_id=business_id,
            published_at=datetime(
                2026,
                7,
                7,
                14,
                0,
                tzinfo=UTC,
            ),
            rating=4.0,
            is_meaningful=True,
        )

        july_second = await _insert_review(
            business_id=business_id,
            published_at=datetime(
                2026,
                7,
                25,
                9,
                0,
                tzinfo=UTC,
            ),
            rating=None,
            is_meaningful=False,
        )

        # August intentionally left empty.

        # ========================================
        # Outside the requested range
        # ========================================
        outside_range_review = await (
            _insert_review(
                business_id=business_id,
                published_at=datetime(
                    2026,
                    9,
                    3,
                    12,
                    0,
                    tzinfo=UTC,
                ),
                rating=5.0,
                is_meaningful=True,
            )
        )

        # ========================================
        # Different business must not appear
        # ========================================
        other_business_review = await (
            _insert_review(
                business_id=other_business_id,
                published_at=datetime(
                    2026,
                    6,
                    10,
                    9,
                    0,
                    tzinfo=UTC,
                ),
                rating=5.0,
                is_meaningful=True,
            )
        )

        inserted_ids = [
            june_first.id,
            june_second.id,
            july_first.id,
            july_second.id,
            outside_range_review.id,
            other_business_review.id,
        ]

        trend = await get_reviews_per_month_trend(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
        )

        assert (
            trend.business_id == business_id
        )

        assert trend.source == "google_maps"

        assert (
            trend.range_start == range_start
        )

        assert trend.range_end == range_end

        assert len(trend.buckets) == 3

        # June
        june_bucket = trend.buckets[0]

        assert (
            june_bucket.month_start
            == date(2026, 6, 1)
        )

        assert june_bucket.review_count == 2

        assert (
            june_bucket.meaningful_review_count
            == 2
        )

        assert (
            june_bucket.rating_average
            == pytest.approx(
                4.0,
            )
        )

        # July
        july_bucket = trend.buckets[1]

        assert (
            july_bucket.month_start
            == date(2026, 7, 1)
        )

        assert july_bucket.review_count == 2

        assert (
            july_bucket.meaningful_review_count
            == 1
        )

        assert (
            july_bucket.rating_average
            == pytest.approx(
                4.0,
            )
        )

        # August (empty)
        august_bucket = trend.buckets[2]

        assert (
            august_bucket.month_start
            == date(2026, 8, 1)
        )

        assert (
            august_bucket.review_count == 0
        )

        assert (
            august_bucket
            .meaningful_review_count
            == 0
        )

        assert (
            august_bucket.rating_average
            is None
        )

        assert trend.total_reviews == 4

        assert (
            trend.total_meaningful_reviews
            == 3
        )

    finally:
        try:
            for review_id in inserted_ids:
                stored_review = (
                    await CustomerReviewDocument
                    .get(
                        review_id
                    )
                )

                if stored_review is not None:
                    await stored_review.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_reviews_trend_rejects_invalid_range():
    """Reject non-strictly-increasing ranges."""

    with pytest.raises(
        ValueError,
    ):
        await get_reviews_per_month_trend(
            business_id=uuid4(),
            range_start=datetime(
                2026,
                7,
                1,
                0,
                0,
                tzinfo=UTC,
            ),
            range_end=datetime(
                2026,
                7,
                1,
                0,
                0,
                tzinfo=UTC,
            ),
        )