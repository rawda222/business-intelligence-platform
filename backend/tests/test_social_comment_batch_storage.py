"""
Social Comment Batch Storage Tests

Verifies batch result counting, continue-on-error behavior,
and strict fail-fast behavior independently from MongoDB.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.normalized_social import (
    NormalizedSocialComment,
)
from app.services import (
    social_comment_storage_service,
)
from app.services.social_comment_storage_service import (
    SocialCommentParentNotFoundError,
    SocialCommentStorageResult,
    store_normalized_social_comments,
)


def build_batch_comment(
    *,
    platform_comment_id: str,
) -> NormalizedSocialComment:
    """Build one valid comment for batch-policy tests."""

    return NormalizedSocialComment(
        business_id=uuid4(),
        social_account_id=uuid4(),
        platform="facebook",
        platform_post_id="batch-parent-post",
        platform_comment_id=platform_comment_id,
        text="Batch comment test",
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
        author_reference="batch-customer",
        information_quality="high",
        is_emoji_only=False,
        connector_type="apify",
        raw_data={
            "source": "batch_test",
        },
    )


@pytest.mark.asyncio
async def test_comment_batch_counts_results_and_continues(
    monkeypatch,
):
    """
    Count created, updated, unchanged, and failed comments.

    One failed comment must not prevent later comments from being
    processed when continue_on_error is True.
    """

    created_comment = build_batch_comment(
        platform_comment_id="created-comment",
    )

    failed_comment = build_batch_comment(
        platform_comment_id="failed-comment",
    )

    updated_comment = build_batch_comment(
        platform_comment_id="updated-comment",
    )

    unchanged_comment = build_batch_comment(
        platform_comment_id="unchanged-comment",
    )

    processed_ids: list[str] = []

    async def fake_store_normalized_social_comment(
        comment,
    ):
        comment_id = (
            comment.platform_comment_id
            or ""
        )

        processed_ids.append(
            comment_id
        )

        if comment_id == "failed-comment":
            raise SocialCommentParentNotFoundError(
                "Simulated missing parent"
            )

        stored_comment = SimpleNamespace(
            platform_comment_id=comment_id,
        )

        if comment_id == "created-comment":
            return SocialCommentStorageResult(
                comment=stored_comment,
                created=True,
                updated=False,
                reason="comment_created",
            )

        if comment_id == "updated-comment":
            return SocialCommentStorageResult(
                comment=stored_comment,
                                created=False,
                updated=True,
                reason="comment_updated",
            )

        return SocialCommentStorageResult(
            comment=stored_comment,
            created=False,
            updated=False,
            reason="comment_already_exists",
        )
    monkeypatch.setattr(
        social_comment_storage_service,
        "store_normalized_social_comment",
        fake_store_normalized_social_comment,
    )

    result = await store_normalized_social_comments(
        [
            created_comment,
            failed_comment,
            updated_comment,
            unchanged_comment,
        ],
        continue_on_error=True,
    )

    assert processed_ids == [
        "created-comment",
        "failed-comment",
        "updated-comment",
        "unchanged-comment",
    ]

    assert result.comments_received == 4
    assert result.comments_succeeded == 3

    assert result.comments_created == 1
    assert result.comments_updated == 1
    assert result.comments_unchanged == 1

    assert len(result.results) == 3
    assert len(result.failures) == 1

    assert result.failures[0] == {
        "platform": "facebook",
        "platform_post_id": "batch-parent-post",
        "platform_comment_id": "failed-comment",
        "error_type": (
            "SocialCommentParentNotFoundError"
        ),
        "error_message": (
            "Simulated missing parent"
        ),
    }

    failure_text = str(
        result.failures[0]
    )

    assert "Batch comment test" not in failure_text
    assert "raw_data" not in failure_text
@pytest.mark.asyncio
async def test_comment_batch_strict_mode_stops_at_failure(
    monkeypatch,
):
    """
    Raise the first error and stop processing later comments when
    continue_on_error is False.
    """

    first_comment = build_batch_comment(
        platform_comment_id="first-comment",
    )

    failed_comment = build_batch_comment(
        platform_comment_id="strict-failure",
    )

    never_processed_comment = build_batch_comment(
        platform_comment_id="never-processed",
    )

    processed_ids: list[str] = []

    async def fake_store_normalized_social_comment(
        comment,
    ):
        comment_id = (
            comment.platform_comment_id
            or ""
        )

        processed_ids.append(
            comment_id
        )

        if comment_id == "strict-failure":
            raise SocialCommentParentNotFoundError(
                "Strict simulated failure"
            )

        return SocialCommentStorageResult(
            comment=SimpleNamespace(
                platform_comment_id=comment_id,
            ),
            created=True,
            updated=False,
            reason="comment_created",
        )

    monkeypatch.setattr(
        social_comment_storage_service,
        "store_normalized_social_comment",
        fake_store_normalized_social_comment,
    )

    with pytest.raises(
        SocialCommentParentNotFoundError,
        match="Strict simulated failure",
    ):
        await store_normalized_social_comments(
            [
                first_comment,
                failed_comment,
                never_processed_comment,
            ],
            continue_on_error=False,
        )

    assert processed_ids == [
        "first-comment",
        "strict-failure",
    ]

    assert (
        "never-processed"
        not in processed_ids
    )
