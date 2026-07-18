"""
Mongo-Backed Cross-Source Customer Voice Loader Tests
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import (
    close_mongo,
    connect_to_mongo,
)
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.services.cross_source_customer_voice_loader import (
    load_cross_source_customer_voice,
)


_RANGE_START = datetime(
    2026,
    7,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    8,
    1,
    tzinfo=UTC,
)


@pytest.mark.asyncio
async def test_loader_is_business_scoped_and_date_scoped():
    """
    Load only customer voice belonging to the requested business
    and the half-open analysis range.
    """

    business_id = uuid4()
    other_business_id = uuid4()
    social_account_id = uuid4()

    parent_post = None
    google_review = None
    facebook_comment = None
    out_of_range_review = None
    other_business_review = None

    try:
        await connect_to_mongo()

        parent_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            platform="facebook",
            platform_post_id=(
                f"post-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                10,
                tzinfo=UTC,
            ),
            text="Brand-owned post",
        )

        await parent_post.insert()

        if parent_post.id is None:
            raise RuntimeError(
                "Parent post was not persisted."
            )

        google_review = (
            CustomerReviewDocument(
                business_id=business_id,
                source="google_maps",
                source_review_id=(
                    f"google-{uuid4().hex}"
                ),
                deduplication_key=(
                    f"google-key-{uuid4().hex}"
                ),
                text=(
                    "Excellent coffee and "
                    "friendly staff"
                ),
                rating=5,
                published_at=datetime(
                    2026,
                    7,
                    5,
                    tzinfo=UTC,
                ),
                information_quality="high",
                is_meaningful=True,
            )
        )

        await google_review.insert()

        facebook_comment = (
            SocialCommentDocument(
                business_id=business_id,
                social_account_id=(
                    social_account_id
                ),
                social_post_id=(
                    parent_post.id
                ),
                platform="facebook",
                platform_post_id=(
                    parent_post
                    .platform_post_id
                ),
                platform_comment_id=(
                    f"comment-{uuid4().hex}"
                ),
                deduplication_key=(
                    f"comment-key-{uuid4().hex}"
                ),
                text=(
                    "Service was very slow"
                ),
                published_at=datetime(
                    2026,
                    7,
                    11,
                    tzinfo=UTC,
                ),
                information_quality="high",
                connector_type="apify",
            )
        )

        await facebook_comment.insert()

        out_of_range_review = (
            CustomerReviewDocument(
                business_id=business_id,
                source="google_maps",
                source_review_id=(
                    f"old-{uuid4().hex}"
                ),
                deduplication_key=(
                    f"old-key-{uuid4().hex}"
                ),
                text="Older review",
                rating=3,
                published_at=datetime(
                    2026,
                    6,
                    20,
                    tzinfo=UTC,
                ),
                information_quality="high",
                is_meaningful=True,
            )
        )

        await out_of_range_review.insert()

        other_business_review = (
            CustomerReviewDocument(
                business_id=(
                    other_business_id
                ),
                source="google_maps",
                source_review_id=(
                    f"other-{uuid4().hex}"
                ),
                deduplication_key=(
                    f"other-key-{uuid4().hex}"
                ),
                text=(
                    "Review from another business"
                ),
                rating=1,
                published_at=datetime(
                    2026,
                    7,
                    12,
                    tzinfo=UTC,
                ),
                information_quality="high",
                is_meaningful=True,
            )
        )

        await other_business_review.insert()

        result = (
            await load_cross_source_customer_voice(
                business_id=business_id,
                business_name="Example Cafe",
                business_type="cafe",
                range_start=_RANGE_START,
                range_end=_RANGE_END,
            )
        )

        assert result.business_id == (
            business_id
        )

        assert result.records_received == 2

        assert result.records_included == 2

        assert result.records_excluded == 0

        assert result.records_by_source == (
            (
                "google_maps",
                1,
            ),
            (
                "facebook_comments",
                1,
            ),
        )

        assert {
            record["source"]
            for record
            in result.business_reviews
        } == {
            "google_maps",
            "facebook_comments",
        }

        assert all(
            record["entity_type"]
            == "target_business"
            for record
            in result.business_reviews
        )

    finally:
        if facebook_comment is not None:
            await facebook_comment.delete()

        if google_review is not None:
            await google_review.delete()

        if out_of_range_review is not None:
            await out_of_range_review.delete()

        if other_business_review is not None:
            await other_business_review.delete()

        if parent_post is not None:
            await parent_post.delete()

        await close_mongo()


@pytest.mark.asyncio
async def test_loader_deduplicates_comment_across_collections():
    """
    The same social comment stored as CustomerReviewDocument and
    SocialCommentDocument must contribute one Theme mention.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    shared_comment_id = (
        f"shared-{uuid4().hex}"
    )

    parent_post = None
    customer_voice_comment = None
    social_comment = None

    try:
        await connect_to_mongo()

        parent_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            platform="instagram",
            platform_post_id=(
                f"post-{uuid4().hex}"
            ),
            published_at=datetime(
                2026,
                7,
                15,
                tzinfo=UTC,
            ),
            text="Brand caption",
        )

        await parent_post.insert()

        if parent_post.id is None:
            raise RuntimeError(
                "Parent post was not persisted."
            )

        customer_voice_comment = (
            CustomerReviewDocument(
                business_id=business_id,
                source="instagram_comments",
                source_review_id=(
                    shared_comment_id
                ),
                deduplication_key=(
                    f"voice-key-{uuid4().hex}"
                ),
                text=(
                    "The dessert was amazing"
                ),
                published_at=datetime(
                    2026,
                    7,
                    16,
                    tzinfo=UTC,
                ),
                information_quality="high",
                is_meaningful=True,
            )
        )

        await customer_voice_comment.insert()

        social_comment = (
            SocialCommentDocument(
                business_id=business_id,
                social_account_id=(
                    social_account_id
                ),
                social_post_id=(
                    parent_post.id
                ),
                platform="instagram",
                platform_post_id=(
                    parent_post
                    .platform_post_id
                ),
                platform_comment_id=(
                    shared_comment_id
                ),
                deduplication_key=(
                    f"social-key-{uuid4().hex}"
                ),
                text=(
                    "The dessert was amazing"
                ),
                published_at=datetime(
                    2026,
                    7,
                    16,
                    tzinfo=UTC,
                ),
                information_quality="high",
                connector_type="apify",
            )
        )

        await social_comment.insert()

        result = (
            await load_cross_source_customer_voice(
                business_id=business_id,
                business_name="Example Cafe",
                business_type="cafe",
                range_start=_RANGE_START,
                range_end=_RANGE_END,
            )
        )

        assert result.records_received == 2

        assert result.records_included == 1

        assert result.duplicate_records == 1

        assert len(
            result.business_reviews
        ) == 1

        assert (
            result.business_reviews[0][
                "review_id"
            ]
            == (
                "instagram:comment:"
                f"{shared_comment_id}"
            )
        )

        assert result.records_by_source == (
            (
                "instagram_comments",
                1,
            ),
        )

    finally:
        if social_comment is not None:
            await social_comment.delete()

        if (
            customer_voice_comment
            is not None
        ):
            await (
                customer_voice_comment
                .delete()
            )

        if parent_post is not None:
            await parent_post.delete()

        await close_mongo()


@pytest.mark.asyncio
async def test_loader_rejects_invalid_range():
    """An empty or reversed date range must fail before querying."""

    business_id = uuid4()

    with pytest.raises(
        ValueError,
        match="range_start",
    ):
        await load_cross_source_customer_voice(
            business_id=business_id,
            business_name="Example Cafe",
            business_type="cafe",
            range_start=_RANGE_END,
            range_end=_RANGE_START,
        )


@pytest.mark.asyncio
async def test_loader_accepts_naive_dates_as_utc():
    """Naive boundaries should be normalized to UTC."""

    business_id = uuid4()

    try:
        await connect_to_mongo()

        result = (
            await load_cross_source_customer_voice(
                business_id=business_id,
                business_name="Example Cafe",
                business_type="cafe",
                range_start=datetime(
                    2026,
                    7,
                    1,
                ),
                range_end=datetime(
                    2026,
                    8,
                    1,
                ),
            )
        )

        assert result.business_id == (
            business_id
        )

        assert result.records_received == 0

        assert result.business_reviews == ()

    finally:
        await close_mongo()