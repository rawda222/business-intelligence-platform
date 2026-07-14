"""
Facebook Normalizer Tests

Verifies Facebook post and comment normalization using fields
matching the actual Facebook collector output.
"""

from datetime import UTC
from uuid import uuid4

import pytest

from app.preprocessing.social.facebook_normalizer import (
    infer_comment_information_quality,
    is_emoji_only_text,
    normalize_facebook_payload,
    normalize_facebook_post,
    parse_facebook_datetime,
    parse_non_negative_integer,
)


def build_facebook_payload() -> dict:
    """Return a Facebook-like payload used across tests."""

    return {
        "source": {
            "platform": "facebook",
            "collected_at": (
                "2026-07-13T16:27:12.771716+00:00"
            ),
        },
        "posts": [
            {
                "id": "1457988579706770",
                "url": (
                    "https://example.test/facebook-post"
                ),
                "text": (
                    "إعلان عن برنامج تدريبي جديد"
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
                        "id": "CommentCaseSensitiveID",
                        "post_url": (
                            "https://example.test/"
                            "facebook-post"
                        ),
                        "text": "امتى التقديم؟",
                        "created_at": (
                            "2026-07-13T16:12:22.000Z"
                        ),
                        "likes_count": 0,
                        "reply_count": 0,
                        "author": {
                            "id": "AuthorReferenceABC",
                            "name": "Example Author",
                            "picture": (
                                "must-not-be-copied"
                            ),
                            "gender": (
                                "must-not-be-copied"
                            ),
                            "work_info": {
                                "private": (
                                    "must-not-be-copied"
                                ),
                            },
                        },
                    },
                    {
                        "id": "comment-emoji",
                        "text": "😍😍😍",
                        "created_at": (
                            "2026-07-13T16:13:00.000Z"
                        ),
                        "likes_count": "0",
                        "reply_count": 0,
                    },
                    {
                        "id": "comment-empty",
                        "text": "   ",
                    },
                ],
            },
            {
                # Invalid post: missing ID.
                "text": "This post must be skipped",
            },
            "invalid-post-value",
        ],
    }


def test_facebook_payload_normalizes_real_post_fields():
    """Map Facebook post fields without losing zero metrics."""

    business_id = uuid4()
    social_account_id = uuid4()

    posts, comments = normalize_facebook_payload(
        build_facebook_payload(),
        business_id=business_id,
        social_account_id=social_account_id,
    )

    assert len(posts) == 1
    assert len(comments) == 2

    post = posts[0]

    assert post.business_id == business_id
    assert post.social_account_id == social_account_id
    assert post.platform == "facebook"

    assert (
        post.platform_post_id
        == "1457988579706770"
    )

    assert (
        post.text
        == "إعلان عن برنامج تدريبي جديد"
    )

    assert post.content_type == "text"

    assert post.metrics.likes is None
    assert post.metrics.reactions == 74
    assert post.metrics.comments == 8
    assert post.metrics.shares == 5

    # Zero is a real observed value, not missing data.
    assert post.metrics.views == 0

    assert post.metrics.captured_at.tzinfo == UTC
    assert post.published_at is not None
    assert post.published_at.tzinfo == UTC

    assert post.connector_type == "apify"

    # Nested comments must not be duplicated inside post raw_data.
    assert "comments" not in post.raw_data


def test_facebook_comments_preserve_quality_and_zero_values():
    """Classify meaningful and emoji-only comments."""

    posts, comments = normalize_facebook_payload(
        build_facebook_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    question_comment = comments[0]
    emoji_comment = comments[1]

    assert question_comment.text == "امتى التقديم؟"
    assert question_comment.information_quality == "high"
    assert question_comment.is_emoji_only is False

    # Numeric zero must remain zero.
    assert question_comment.like_count == 0
    assert question_comment.reply_count == 0

    assert (
        question_comment.platform_comment_id
        == "CommentCaseSensitiveID"
    )

    assert (
        question_comment.author_reference
        == "AuthorReferenceABC"
    )

    assert emoji_comment.text == "😍😍😍"
    assert emoji_comment.information_quality == "low"
    assert emoji_comment.is_emoji_only is True
    assert emoji_comment.like_count == 0


def test_facebook_comment_raw_data_is_minimized():
    """Do not copy unnecessary author profile data."""

    _, comments = normalize_facebook_payload(
        build_facebook_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    raw_data = comments[0].raw_data

    assert raw_data == {
        "source_platform": "facebook",
        "source_comment_id": (
            "CommentCaseSensitiveID"
        ),
        "post_url": (
            "https://example.test/facebook-post"
        ),
    }

    serialized = str(raw_data)

    assert "picture" not in serialized
    assert "gender" not in serialized
    assert "work_info" not in serialized
    assert "must-not-be-copied" not in serialized


def test_invalid_posts_and_empty_comments_are_skipped():
    """One malformed record must not discard the whole payload."""

    posts, comments = normalize_facebook_payload(
        build_facebook_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    assert len(posts) == 1
    assert len(comments) == 2

    assert all(
        comment.text.strip()
        for comment in comments
    )


def test_post_without_id_is_rejected_directly():
    """Direct post normalization requires an external ID."""

    with pytest.raises(
        ValueError,
        match="missing a usable id",
    ):
        normalize_facebook_post(
            {
                "text": "Missing post ID",
            },
            business_id=uuid4(),
            social_account_id=uuid4(),
            collected_at=parse_facebook_datetime(
                "2026-07-13T16:27:12Z"
            ),
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        ("0", 0),
        (15, 15),
        ("15", 15),
        (None, None),
        ("invalid", None),
        (-1, None),
        (True, None),
    ],
)
def test_non_negative_integer_parsing(
    value,
    expected,
):
    """Parse collector numbers without losing valid zeros."""

    assert (
        parse_non_negative_integer(value)
        == expected
    )


@pytest.mark.parametrize(
    ("text", "expected_quality"),
    [
        ("امتى التقديم؟", "high"),
        (
            "المفروض ميعادنا بكره ولم تصل التفاصيل",
            "high",
        ),
        ("بالتوفيق دايما", "medium"),
        ("رائع", "low"),
        ("😍😍😍", "low"),
    ],
)
def test_comment_information_quality(
    text,
    expected_quality,
):
    """Classify structural richness, not sentiment."""

    assert (
        infer_comment_information_quality(text)
        == expected_quality
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("😍😍😍", True),
        ("!!!", True),
        ("امتى؟", False),
        ("Great!", False),
        ("123", False),
    ],
)
def test_emoji_only_detection(
    text,
    expected,
):
    """Detect comments without letters or digits."""

    assert is_emoji_only_text(text) is expected
