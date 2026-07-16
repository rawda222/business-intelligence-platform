"""
Trend Foundation Service Tests

Verifies tenant-scoped foundational statistics using previously
built payload processing services.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.services.customer_review_payload_processing_service import (
    process_customer_review_payload,
)
from app.services.social_payload_processing_service import (
    process_facebook_payload,
)
from app.services.trend_foundation_service import (
    get_business_trend_foundation_stats,
)


def build_facebook_payload(
    *,
    unique_suffix: str,
) -> dict:
    """Return a Facebook-style payload for foundation tests."""

    return {
        "source": {
            "collected_at": (
                "2026-07-13T16:27:12.771716+00:00"
            ),
        },
        "posts": [
            {
                "id": (
                    "foundation-post-"
                    f"{unique_suffix}"
                ),
                "url": (
                    "https://example.test/"
                    "foundation-post"
                ),
                "text": (
                    "منشور تجريبي "
                    "لإحصائيات التريند"
                ),
                "created_at": (
                    "2026-07-09T11:31:46.000Z"
                ),
                "type": None,
                "reactions_count": 74,
                "comments_count": 8,
                "shares_count": 5,
                "views_count": 0,
                "image_url": None,
                "video_url": None,
                "external_url": None,
                "comments": [
                    {
                        "id": (
                            "foundation-comment-"
                            f"{unique_suffix}"
                        ),
                        "post_url": (
                            "https://example.test/"
                            "foundation-post"
                        ),
                        "text": (
                            "امتى التقديم؟"
                        ),
                        "created_at": (
                            "2026-07-13T16:12:22"
                            ".000Z"
                        ),
                        "likes_count": 0,
                        "reply_count": 0,
                        "author": {
                            "id": (
                                "foundation-"
                                "author"
                            ),
                            "name": (
                                "Example Author"
                            ),
                        },
                    },
                ],
            },
        ],
    }


def build_review_payload(
    *,
    unique_suffix: str,
) -> dict:
    """Return a Volume-style review payload for tests."""

    return {
        "reviews": {
            "summary": {
                "total_reviews": 2,
            },
            "raw_samples": [
                {
                    "id": (
                        "foundation-review-a-"
                        f"{unique_suffix}"
                    ),
                    "text": (
                        "{'ar': 'الخدمة "
                        "ممتازة والقهوة رائعة'}"
                    ),
                    "rating": 5,
                    "source": "google_maps",
                },
                {
                    "id": (
                        "foundation-review-b-"
                        f"{unique_suffix}"
                    ),
                    "text": (
                        "{'ar': 'الأسعار "
                        "مناسبة والمكان "
                        "هادئ'}"
                    ),
                    "rating": 4,
                    "source": "google_maps",
                },
            ],
        },
    }


@pytest.mark.asyncio
async def test_trend_foundation_stats_are_business_scoped():
    """Compute per-business statistics without leaking across tenants."""

    business_id = uuid4()
    other_business_id = uuid4()
    social_account_id = uuid4()

    unique_suffix = uuid4().hex

    facebook_payload = build_facebook_payload(
        unique_suffix=unique_suffix,
    )

    review_payload = build_review_payload(
        unique_suffix=unique_suffix,
    )

    stored_post_ids = []
    stored_comment_ids = []
    stored_review_ids = []

    try:
        await connect_to_mongo()

        facebook_result = (
            await process_facebook_payload(
                facebook_payload,
                business_id=business_id,
                social_account_id=(
                    social_account_id
                ),
                connector_type="apify",
            )
        )

        stored_post_ids = [
            item.post.id
            for item in (
                facebook_result.storage.results
            )
            if item.post.id is not None
        ]

        stored_comment_ids = [
            item.comment.id
            for item in (
                facebook_result
                .comment_storage
                .results
            )
            if item.comment.id is not None
        ]

        review_result = (
            await process_customer_review_payload(
                review_payload,
                business_id=business_id,
                source="google_maps",
                collected_at=datetime(
                    2026,
                    7,
                    15,
                    18,
                    0,
                    tzinfo=UTC,
                ),
            )
        )

        stored_review_ids = [
            item.review.id
            for item in (
                review_result.storage.results
            )
            if item.review.id is not None
        ]

        stats = await (
            get_business_trend_foundation_stats(
                business_id
            )
        )

        assert (
            stats.business_id == business_id
        )

        assert stats.total_posts == 1

        assert (
            stats.total_post_metric_snapshots
            >= 1
        )

        assert stats.total_comments == 1
        assert stats.total_customer_reviews == 2

        assert stats.posts_by_platform == {
            "facebook": 1,
        }

        assert (
            stats.comments_by_platform
            == {
                "facebook": 1,
            }
        )

        assert stats.reviews_by_source == {
            "google_maps": 2,
        }

        # ====================================================
        # Different Business Sees Nothing
        # ====================================================
        other_stats = await (
            get_business_trend_foundation_stats(
                other_business_id
            )
        )

        assert other_stats.total_posts == 0

        assert (
            other_stats
            .total_post_metric_snapshots
            == 0
        )

        assert (
            other_stats.total_comments == 0
        )

        assert (
            other_stats
            .total_customer_reviews
            == 0
        )

        assert (
            other_stats.posts_by_platform
            == {}
        )

        assert (
            other_stats.comments_by_platform
            == {}
        )

        assert (
            other_stats.reviews_by_source
            == {}
        )

    finally:
        try:
            for comment_id in stored_comment_ids:
                stored_comment = (
                    await SocialCommentDocument
                    .get(
                        comment_id
                    )
                )

                if stored_comment is not None:
                    await (
                        stored_comment.delete()
                    )

            for review_id in stored_review_ids:
                stored_review = (
                    await CustomerReviewDocument
                    .get(
                        review_id
                    )
                )

                if stored_review is not None:
                    await (
                        stored_review.delete()
                    )

            for post_id in stored_post_ids:
                await (
                    PostMetricSnapshotDocument
                    .find(
                        PostMetricSnapshotDocument
                        .social_post_id
                        == post_id
                    )
                    .delete()
                )

                stored_post = (
                    await SocialPostDocument.get(
                        post_id
                    )
                )

                if stored_post is not None:
                    await stored_post.delete()

        finally:
            await close_mongo()