from uuid import uuid4

import pytest
from datetime import UTC, datetime

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    NormalizedSocialComment,
)
from app.services.social_comment_storage_service import (
    SocialCommentParentNotFoundError,
    store_normalized_social_comment,
)


def build_storage_comment(
    *,
    business_id,
    social_account_id,
    platform_post_id: str,
    platform_comment_id: str | None,
) -> NormalizedSocialComment:
    """
    Build one normalized comment for persistence tests.
    """

    return NormalizedSocialComment(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="facebook",
        platform_post_id=platform_post_id,
        platform_comment_id=platform_comment_id,
        text="الخدمة ممتازة وسريعة",
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
        like_count=3,
        reply_count=1,
        author_reference="customer-1",
        information_quality="high",
        is_emoji_only=False,
        connector_type="apify",
        raw_data={
            "source": "comment_storage_test",
        },
    )


@pytest.mark.asyncio
async def test_comment_is_created_and_duplicate_is_suppressed():
    """
    Store one comment and return the same document on repetition.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    platform_post_id = (
        f"comment-storage-post-{uuid4().hex}"
    )

    stored_post = None
    stored_comment_id = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=datetime(
                2026,
                7,
                15,
                16,
                0,
                tzinfo=UTC,
            ),
            content_type="text",
            text="Parent post",
            connector_type="apify",
            raw_data={
                "source": "comment_storage_test",
            },
        )

        await stored_post.insert()

        normalized_comment = build_storage_comment(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=platform_post_id,
            platform_comment_id="comment-123",
        )

        first_result = (
            await store_normalized_social_comment(
                normalized_comment
            )
        )

        stored_comment_id = (
            first_result.comment.id
        )

        assert stored_comment_id is not None

        assert first_result.created is True
        assert first_result.updated is False

        assert (
            first_result.reason
            == "comment_created"
        )

        assert (
            first_result.comment.business_id
            == business_id
        )

        assert (
            first_result.comment.social_account_id
            == social_account_id
        )

        assert (
            first_result.comment.social_post_id
            == stored_post.id
        )

        assert (
            first_result.comment.platform
            == "facebook"
        )

        assert (
            first_result.comment.platform_post_id
            == platform_post_id
        )

        assert (
            first_result.comment.platform_comment_id
            == "comment-123"
        )

        assert (
            first_result.comment.deduplication_key
            == "id:comment-123"
        )

        assert (
            first_result.comment.text
            == "الخدمة ممتازة وسريعة"
        )

        assert (
            first_result.comment.like_count
            == 3
        )

        assert (
            first_result.comment.reply_count
            == 1
        )

        assert (
            first_result.comment.author_reference
            == "customer-1"
        )

        assert (
            first_result.comment.information_quality
            == "high"
        )

        assert (
            first_result.comment.is_emoji_only
            is False
        )

        assert (
            first_result.comment.connector_type
            == "apify"
        )

        assert first_result.comment.raw_data == {
            "source": "comment_storage_test",
        }

        # ====================================================
        # Same Observation Must Not Create a Duplicate
        # ====================================================
        second_result = (
            await store_normalized_social_comment(
                normalized_comment
            )
        )

        assert second_result.created is False
        assert second_result.updated is False

        assert (
            second_result.reason
            == "comment_already_exists"
        )

        assert (
            second_result.comment.id
            == stored_comment_id
        )

        count = await (
            SocialCommentDocument.find(
                SocialCommentDocument.business_id
                == business_id,
                SocialCommentDocument.social_account_id
                == social_account_id,
                SocialCommentDocument.platform
                == "facebook",
                SocialCommentDocument.deduplication_key
                == "id:comment-123",
            ).count()
        )

        assert count == 1

        persisted_comment = (
            await SocialCommentDocument.get(
                stored_comment_id
            )
        )

        assert persisted_comment is not None

        assert (
            persisted_comment.social_post_id
            == stored_post.id
        )

    finally:
        try:
            if stored_comment_id is not None:
                stored_comment = (
                    await SocialCommentDocument.get(
                        stored_comment_id
                    )
                )

                if stored_comment is not None:
                    await stored_comment.delete()

            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                persisted_post = (
                    await SocialPostDocument.get(
                        stored_post.id
                    )
                )

                if persisted_post is not None:
                    await persisted_post.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_comment_without_external_id_is_deduplicated():
    """
    Use the deterministic SHA-256 fallback identity when the
    platform does not provide a comment ID.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    platform_post_id = (
        f"fallback-comment-post-{uuid4().hex}"
    )

    stored_post = None
    stored_comment_id = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=datetime(
                2026,
                7,
                15,
                16,
                0,
                tzinfo=UTC,
            ),
            content_type="text",
            text="Fallback identity parent post",
            connector_type="apify",
            raw_data={
                "source": "comment_storage_test",
            },
        )

        await stored_post.insert()

        normalized_comment = build_storage_comment(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=platform_post_id,
            platform_comment_id=None,
        )

        first_result = (
            await store_normalized_social_comment(
                normalized_comment
            )
        )

        stored_comment_id = (
            first_result.comment.id
        )

        assert stored_comment_id is not None
        assert first_result.created is True

        assert (
            first_result.comment.platform_comment_id
            is None
        )

        assert (
            first_result.comment.deduplication_key
            .startswith("sha256:")
        )

        second_result = (
            await store_normalized_social_comment(
                normalized_comment
            )
        )

        assert second_result.created is False

        assert (
            second_result.comment.id
            == stored_comment_id
        )

        count = await (
            SocialCommentDocument.find(
                SocialCommentDocument.social_post_id
                == stored_post.id
            ).count()
        )

        assert count == 1

    finally:
        try:
            if stored_comment_id is not None:
                stored_comment = (
                    await SocialCommentDocument.get(
                        stored_comment_id
                    )
                )

                if stored_comment is not None:
                    await stored_comment.delete()

            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                persisted_post = (
                    await SocialPostDocument.get(
                        stored_post.id
                    )
                )

                if persisted_post is not None:
                    await persisted_post.delete()
        finally:
            await close_mongo()


@pytest.mark.asyncio
async def test_orphan_comment_is_rejected():
    """
    Reject a comment when its tenant-scoped parent post is missing.
    """

    try:
        await connect_to_mongo()

        comment = build_storage_comment(
            business_id=uuid4(),
            social_account_id=uuid4(),
            platform_post_id=(
                f"missing-parent-{uuid4().hex}"
            ),
            platform_comment_id=None,
        )

        with pytest.raises(
            SocialCommentParentNotFoundError,
            match=(
                "tenant-scoped parent post "
                "was not found"
            ),
        ):
            await store_normalized_social_comment(
                comment
            )

    finally:
        await close_mongo()

@pytest.mark.asyncio
async def test_existing_comment_is_updated_safely():
    """
    Update mutable comment observations without creating a duplicate.

    A repeated external comment ID identifies the same comment.
    New counts and quality information update the stored document,
    while missing optional values do not erase useful stored data.
    """

    business_id = uuid4()
    social_account_id = uuid4()

    platform_post_id = (
        f"comment-update-post-{uuid4().hex}"
    )

    stored_post = None
    stored_comment_id = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_id,
            social_account_id=social_account_id,
            platform="facebook",
            platform_post_id=platform_post_id,
            published_at=datetime(
                2026,
                7,
                15,
                16,
                0,
                tzinfo=UTC,
            ),
            content_type="text",
            text="Parent post for comment update",
            connector_type="apify",
            raw_data={
                "source": "comment_update_test",
            },
        )

        await stored_post.insert()

        original_comment = build_storage_comment(
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=platform_post_id,
            platform_comment_id="update-comment-123",
        )

        first_result = (
            await store_normalized_social_comment(
                original_comment
            )
        )

        stored_comment_id = (
            first_result.comment.id
        )

        assert stored_comment_id is not None
        assert first_result.created is True
        assert first_result.updated is False

        assert (
            first_result.reason
            == "comment_created"
        )

        # ====================================================
        # Same Identity with New Mutable Observations
        # ====================================================
        updated_comment = (
            original_comment.model_copy(
                update={
                    "published_at": None,
                    "like_count": 7,
                    "reply_count": 2,
                    "author_reference": None,
                    "information_quality": "medium",
                    "raw_data": {
                        "new_observation": True,
                        "ignored_none": None,
                    },
                },
            )
        )

        second_result = (
            await store_normalized_social_comment(
                updated_comment
            )
        )

        assert second_result.created is False
        assert second_result.updated is True

        assert (
            second_result.reason
            == "comment_updated"
        )

        assert (
            second_result.comment.id
            == stored_comment_id
        )

        assert (
            second_result.comment.like_count
            == 7
        )

        assert (
            second_result.comment.reply_count
            == 2
        )

        assert (
            second_result.comment.information_quality
            == "medium"
        )

        # None must not erase useful stored fields.
        assert (
            second_result.comment.author_reference
            == "customer-1"
        )

        assert (
            second_result.comment.published_at
            is not None
        )

        # Existing raw_data is preserved and new data is merged.
        assert second_result.comment.raw_data == {
            "source": "comment_storage_test",
            "new_observation": True,
        }

        assert (
            second_result.comment.updated_at
            is not None
        )

        assert (
            second_result.comment.collected_at
            is not None
        )

        count = await (
            SocialCommentDocument.find(
                SocialCommentDocument.business_id
                == business_id,
                SocialCommentDocument.social_account_id
                == social_account_id,
                SocialCommentDocument.platform
                == "facebook",
                SocialCommentDocument.deduplication_key
                == "id:update-comment-123",
            ).count()
        )

        # Safe update must not create a second document.
        assert count == 1

        # ====================================================
        # Repeating the Updated Observation Is Idempotent
        # ====================================================
        third_result = (
            await store_normalized_social_comment(
                updated_comment
            )
        )

        assert third_result.created is False
        assert third_result.updated is False

        assert (
            third_result.reason
            == "comment_already_exists"
        )

        assert (
            third_result.comment.id
            == stored_comment_id
        )

    finally:
        try:
            if stored_comment_id is not None:
                stored_comment = (
                    await SocialCommentDocument.get(
                        stored_comment_id
                    )
                )

                if stored_comment is not None:
                    await stored_comment.delete()

            if (
                stored_post is not None
                and stored_post.id is not None
            ):
                persisted_post = (
                    await SocialPostDocument.get(
                        stored_post.id
                    )
                )

                if persisted_post is not None:
                    await persisted_post.delete()
        finally:
            await close_mongo()