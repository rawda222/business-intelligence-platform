"""
Social Comment Parent Lookup Tests

Verifies that normalized comments resolve their MongoDB parent post
only inside the exact tenant, account, platform, and post scope.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.mongo import close_mongo, connect_to_mongo
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    NormalizedSocialComment,
)
from app.services.social_comment_storage_service import (
    find_comment_parent_post,
)


def build_lookup_comment(
    *,
    business_id,
    social_account_id,
    platform: str,
    platform_post_id: str,
) -> NormalizedSocialComment:
    """
    Build one normalized comment for parent lookup tests.
    """

    return NormalizedSocialComment(
        business_id=business_id,
        social_account_id=social_account_id,
        platform=platform,
        platform_post_id=platform_post_id,
        platform_comment_id=(
            f"lookup-comment-{uuid4().hex}"
        ),
        text="Parent post lookup test comment",
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
        like_count=0,
        reply_count=0,
        author_reference="lookup-customer",
        information_quality="high",
        is_emoji_only=False,
        connector_type="apify",
        raw_data={
            "source": "parent_lookup_test",
        },
    )


@pytest.mark.asyncio
async def test_comment_parent_lookup_preserves_tenant_scope():
    """
    Match the parent post only when every scope field matches.

    Required scope:

    - business_id
    - social_account_id
    - platform
    - platform_post_id
    """

    business_a_id = uuid4()
    business_b_id = uuid4()

    social_account_a_id = uuid4()
    social_account_b_id = uuid4()

    platform_post_id = (
        f"comment-parent-{uuid4().hex}"
    )

    stored_post = None

    try:
        await connect_to_mongo()

        stored_post = SocialPostDocument(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
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
            text="Parent post for comment lookup",
            connector_type="apify",
            raw_data={
                "source": "parent_lookup_test",
            },
            collected_at=datetime(
                2026,
                7,
                15,
                18,
                0,
                tzinfo=UTC,
            ),
        )

        await stored_post.insert()

        # ====================================================
        # Exact Scope Must Match
        # ====================================================
        matching_comment = build_lookup_comment(
            business_id=business_a_id,
            social_account_id=social_account_a_id,
            platform="facebook",
            platform_post_id=platform_post_id,
        )

        match = await find_comment_parent_post(
            matching_comment
        )

        assert match is not None
        assert match.id == stored_post.id

        assert (
            match.business_id
            == business_a_id
        )

        assert (
            match.social_account_id
            == social_account_a_id
        )

        # ====================================================
        # Different Business Must Not Match
        # ====================================================
        different_business_comment = (
            matching_comment.model_copy(
                update={
                    "business_id": business_b_id,
                },
            )
        )

        assert (
            await find_comment_parent_post(
                different_business_comment
            )
            is None
        )

        # ====================================================
        # Different Social Account Must Not Match
        # ====================================================
        different_account_comment = (
            matching_comment.model_copy(
                update={
                    "social_account_id": (
                        social_account_b_id
                    ),
                },
            )
        )

        assert (
            await find_comment_parent_post(
                different_account_comment
            )
            is None
        )

        # ====================================================
        # Different Platform Must Not Match
        # ====================================================
        different_platform_comment = (
            matching_comment.model_copy(
                update={
                    "platform": "instagram",
                },
            )
        )

        assert (
            await find_comment_parent_post(
                different_platform_comment
            )
            is None
        )

        # ====================================================
        # Different External Post ID Must Not Match
        # ====================================================
        different_post_comment = (
            matching_comment.model_copy(
                update={
                    "platform_post_id": (
                        "different-platform-post-id"
                    ),
                },
            )
        )

        assert (
            await find_comment_parent_post(
                different_post_comment
            )
            is None
        )

    finally:
        try:
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
async def test_comment_parent_lookup_returns_none_when_post_missing():
    """
    Return None when no parent post exists in MongoDB.
    """

    try:
        await connect_to_mongo()

        missing_comment = build_lookup_comment(
            business_id=uuid4(),
            social_account_id=uuid4(),
            platform="instagram",
            platform_post_id=(
                f"missing-parent-{uuid4().hex}"
            ),
        )

        assert (
            await find_comment_parent_post(
                missing_comment
            )
            is None
        )

    finally:
        await close_mongo()