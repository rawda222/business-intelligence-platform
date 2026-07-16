"""
Business Trend Report Service Tests

Verifies that build_business_trend_report aggregates every trend
surface for one business without leaking across tenants.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)
from app.services.business_trend_report_service import (
    build_business_trend_report,
)
from app.services.customer_review_storage_service import (
    build_customer_review_deduplication_key,
    create_customer_review,
)
from app.services.post_metric_service import (
    record_metric_snapshot,
)


@pytest.mark.asyncio
async def test_business_trend_report_aggregates_trends():
    """
    Build a report that combines foundation, posts, reviews, and
    engagement curves for one business.
    """

    business_id = uuid4()
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

    post = None
    stored_review_id = None

    try:
        await connect_to_mongo()

        published_at = datetime(
            2026,
            7,
            7,
            10,
            0,
            tzinfo=UTC,
        )

        post = SocialPostDocument(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            platform="facebook",
            platform_post_id=(
                f"report-post-{uuid4().hex}"
            ),
            published_at=published_at,
            content_type="text",
            text="Report test post",
            connector_type="apify",
            raw_data={
                "source": (
                    "trend_report_test"
                ),
            },
        )

        await post.insert()

        first_capture_at = (
            published_at + timedelta(hours=2)
        )

        second_capture_at = (
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
            captured_at=first_capture_at,
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
            captured_at=second_capture_at,
        )

        # ============================================
        # Customer Review
        # ============================================
        from app.schemas.normalized_social import (
            NormalizedCustomerReview,
        )

        review = NormalizedCustomerReview(
            business_id=business_id,
            source="google_maps",
            source_review_id=(
                f"report-review-{uuid4().hex}"
            ),
            text=(
                "خدمة ممتازة والقهوة رائعة"
            ),
            language="ar",
            rating=5.0,
            published_at=datetime(
                2026,
                7,
                8,
                18,
                0,
                tzinfo=UTC,
            ),
            collected_at=datetime(
                2026,
                7,
                8,
                20,
                0,
                tzinfo=UTC,
            ),
            information_quality="high",
            is_meaningful=True,
            is_emoji_only=False,
            raw_data={
                "source": (
                    "trend_report_test"
                ),
            },
        )

        stored_review = (
            await create_customer_review(
                review=review,
                deduplication_key=(
                    build_customer_review_deduplication_key(
                        review,
                    )
                ),
            )
        )

        stored_review_id = stored_review.id

        # ============================================
        # Build Report
        # ============================================
        report = await build_business_trend_report(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
        )

        assert (
            report.business_id == business_id
        )

        assert (
            report.range_start == range_start
        )

        assert report.range_end == range_end
        assert (
            report.review_source
            == "google_maps"
        )

        # Foundation
        assert (
            report.foundation.total_posts
            == 1
        )

        assert (
            report.foundation
            .total_customer_reviews
            == 1
        )

        # Posts per week
        assert (
            report.posts_per_week.total_posts
            == 1
        )

        # Reviews per month
        assert (
            report.reviews_per_month
            .total_reviews
            == 1
        )

        # Engagement curves
        assert (
            len(report.engagement_curves)
            == 1
        )

        curve = report.engagement_curves[0]

        assert (
            curve.social_post_id
            == post.id
        )

        assert len(curve.points) >= 1

    finally:
        try:
            if stored_review_id is not None:
                stored_review = (
                    await CustomerReviewDocument
                    .get(
                        stored_review_id,
                    )
                )

                if stored_review is not None:
                    await stored_review.delete()

            if (
                post is not None
                and post.id is not None
            ):
                await (
                    PostMetricSnapshotDocument
                    .find(
                        PostMetricSnapshotDocument
                        .social_post_id
                        == post.id,
                    )
                    .delete()
                )

                stored_post = (
                    await SocialPostDocument
                    .get(
                        post.id,
                    )
                )

                if stored_post is not None:
                    await stored_post.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_report_rejects_invalid_range():
    """Reject non-strictly-increasing ranges."""

    with pytest.raises(
        ValueError,
    ):
        await build_business_trend_report(
            business_id=uuid4(),
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