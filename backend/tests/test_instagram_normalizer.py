"""
Instagram Normalizer Tests

Verifies Instagram post and sampled-comment normalization using
fields that match the actual Instagram collector output.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.preprocessing.social.instagram_normalizer import (
    extract_instagram_media_urls,
    normalize_instagram_content_type,
    normalize_instagram_payload,
    normalize_instagram_post,
)


def build_instagram_payload() -> dict:
    """
    Return an Instagram-like payload used across tests.

    The structure mirrors the collector output:

    - profile.scraped_at
    - posts[].shortcode
    - caption
    - posted_at
    - likes
    - comments_count
    - media
    - hashtags
    - mentions
    - tagged_accounts
    - sample_comments
    """

    return {
        "profile": {
            "username": "shein.by.lola",
            "followers": 19113,
            "following": 30,
            "post_count": 1013,
            "is_business_account": True,
            "scraped_at": (
                "2026-07-13T17:33:50.750093"
            ),
        },
        "posts": [
            {
                "shortcode": "DZuTXx3jBxd",
                "url": (
                    "https://www.instagram.com/"
                    "p/DZuTXx3jBxd/"
                ),
                "caption": (
                    "Beautiful Reem available by order"
                ),
                "posted_at": (
                    "2026-06-18T10:13:53Z"
                ),
                "likes": 105,
                "comments_count": 4,
                "media": {
                    "media_type": "carousel",
                    "image_urls": [
                        "https://example.test/image-1.jpg",
                        "https://example.test/image-2.jpg",
                    ],
                    "video_urls": [
                        "https://example.test/video-1.mp4",
                        "https://example.test/image-1.jpg",
                    ],
                    "carousel_item_count": 3,
                },
                "hashtags": [
                    "#Fashion",
                    "fashion",
                    "#Available",
                    "",
                ],
                "mentions": [
                    "@example",
                    "example",
                ],
                "tagged_accounts": [
                    "@model_account",
                    "model_account",
                ],
                "location_name": None,
                "is_pinned": None,
                "comments_sampled": True,
                "sample_comments": [
                    {
                        "author_username": (
                            "janaaabdoo_"
                        ),
                        "text": "😍😍😍😍",
                        "posted_at": (
                            "2026-06-18T12:18:43Z"
                        ),
                        "like_count": 0,
                    },
                    {
                        "author_username": (
                            "CustomerCaseSensitive"
                        ),
                        "text": (
                            "الطلب وصل بسرعة والخامة جميلة"
                        ),
                        "posted_at": (
                            "2026-06-18T12:20:00Z"
                        ),
                        "like_count": 0,
                    },
                    {
                        "author_username": "empty_comment",
                        "text": "   ",
                    },
                    "invalid-comment-value",
                ],
            },
            {
                # A valid image post verifies fallback behavior.
                "shortcode": "ImagePostABC",
                "url": (
                    "https://www.instagram.com/"
                    "p/ImagePostABC/"
                ),
                "caption": "Single image post",
                "posted_at": (
                    "2026-06-19T10:31:54Z"
                ),
                "likes": 0,
                "comments_count": 0,
                "media": {
                    "media_type": None,
                    "image_urls": [
                        "https://example.test/single-image.jpg",
                    ],
                    "video_urls": [],
                    "carousel_item_count": 1,
                },
                "hashtags": [],
                "mentions": [],
                "tagged_accounts": [],
                "comments_sampled": True,
                "sample_comments": [],
            },
            {
                # Invalid post: missing shortcode and ID.
                "caption": "This post must be skipped",
            },
            "invalid-post-value",
        ],
    }


def test_instagram_payload_normalizes_real_post_fields():
    """Map actual Instagram post fields to unified contracts."""

    business_id = uuid4()
    social_account_id = uuid4()

    posts, comments = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=business_id,
        social_account_id=social_account_id,
    )

    assert len(posts) == 2
    assert len(comments) == 2

    carousel_post = posts[0]

    assert carousel_post.business_id == business_id

    assert (
        carousel_post.social_account_id
        == social_account_id
    )

    assert carousel_post.platform == "instagram"

    # Instagram shortcode case must remain unchanged.
    assert (
        carousel_post.platform_post_id
        == "DZuTXx3jBxd"
    )

    assert (
        carousel_post.text
        == "Beautiful Reem available by order"
    )

    assert carousel_post.content_type == "carousel"

    assert carousel_post.media_urls == [
        "https://example.test/image-1.jpg",
        "https://example.test/image-2.jpg",
        "https://example.test/video-1.mp4",
    ]

    assert carousel_post.hashtags == [
        "Fashion",
        "Available",
    ]

    assert carousel_post.mentions == [
        "example",
    ]

    assert carousel_post.tagged_accounts == [
        "model_account",
    ]

    assert carousel_post.metrics.likes == 105

    # comments_count is the reported total, not the number of
    # sampled comments available in the payload.
    assert carousel_post.metrics.comments == 4

    assert carousel_post.metrics.reactions is None
    assert carousel_post.metrics.shares is None

    assert carousel_post.metrics.captured_at.tzinfo == UTC

    assert carousel_post.published_at is not None
    assert carousel_post.published_at.tzinfo == UTC

    assert carousel_post.connector_type == "apify"


def test_instagram_preserves_zero_metrics():
    """Zero likes and comments are observations, not missing data."""

    posts, _ = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    image_post = posts[1]

    assert (
        image_post.platform_post_id
        == "ImagePostABC"
    )

    assert image_post.content_type == "image"
    assert image_post.metrics.likes == 0
    assert image_post.metrics.comments == 0


def test_instagram_comments_preserve_quality_and_zero_values():
    """Classify emoji and meaningful sampled comments."""

    _, comments = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    emoji_comment = comments[0]
    meaningful_comment = comments[1]

    assert emoji_comment.text == "😍😍😍😍"
    assert emoji_comment.information_quality == "low"
    assert emoji_comment.is_emoji_only is True
    assert emoji_comment.like_count == 0

    assert (
        emoji_comment.author_reference
        == "janaaabdoo_"
    )

    assert (
        meaningful_comment.text
        == "الطلب وصل بسرعة والخامة جميلة"
    )

    assert (
        meaningful_comment.information_quality
        == "high"
    )

    assert meaningful_comment.is_emoji_only is False
    assert meaningful_comment.like_count == 0

    # External usernames preserve original case.
    assert (
        meaningful_comment.author_reference
        == "CustomerCaseSensitive"
    )

    assert meaningful_comment.published_at is not None
    assert meaningful_comment.published_at.tzinfo == UTC


def test_instagram_comment_raw_data_is_minimized():
    """Do not duplicate usernames or profile data in raw_data."""

    _, comments = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    assert comments[0].raw_data == {
        "source_platform": "instagram",
    }

    serialized = str(comments[0].raw_data)

    assert "author_username" not in serialized
    assert "profile_image" not in serialized
    assert "biography" not in serialized


def test_instagram_post_raw_data_is_minimized():
    """Keep structural traceability without nested content."""

    posts, _ = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    raw_data = posts[0].raw_data

    assert raw_data == {
        "source_platform": "instagram",
        "source_post_id": "DZuTXx3jBxd",
        "source_post_url": (
            "https://www.instagram.com/"
            "p/DZuTXx3jBxd/"
        ),
        "raw_media_type": "carousel",
        "carousel_item_count": 3,
        "comments_sampled": True,
    }

    assert "sample_comments" not in raw_data
    assert "image_urls" not in raw_data
    assert "video_urls" not in raw_data


def test_invalid_posts_and_empty_comments_are_skipped():
    """Malformed records must not discard the whole payload."""

    posts, comments = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
    )

    assert len(posts) == 2
    assert len(comments) == 2

    assert all(
        comment.text.strip()
        for comment in comments
    )


def test_post_without_shortcode_is_rejected_directly():
    """Direct post normalization requires a stable external ID."""

    with pytest.raises(
        ValueError,
        match="missing a usable shortcode",
    ):
        normalize_instagram_post(
            {
                "caption": "Missing shortcode",
            },
            business_id=uuid4(),
            social_account_id=uuid4(),
            collected_at=datetime.now(UTC),
        )


def test_explicit_collected_at_overrides_profile_scraped_at():
    """Collection workflow time has priority over profile time."""

    explicit_time = datetime(
        2026,
        7,
        14,
        12,
        0,
        tzinfo=UTC,
    )

    posts, _ = normalize_instagram_payload(
        build_instagram_payload(),
        business_id=uuid4(),
        social_account_id=uuid4(),
        collected_at=explicit_time,
    )

    assert all(
        post.metrics.captured_at == explicit_time
        for post in posts
    )


@pytest.mark.parametrize(
    (
        "raw_type",
        "image_urls",
        "video_urls",
        "carousel_count",
        "expected",
    ),
    [
        (
            "carousel",
            ["image-1"],
            [],
            1,
            "carousel",
        ),
        (
            "reel",
            [],
            ["video-1"],
            1,
            "reel",
        ),
        (
            "video",
            [],
            ["video-1"],
            1,
            "video",
        ),
        (
            "image",
            ["image-1"],
            [],
            1,
            "image",
        ),
        (
            None,
            ["image-1", "image-2"],
            [],
            2,
            "carousel",
        ),
        (
            None,
            [],
            ["video-1"],
            1,
            "video",
        ),
        (
            None,
            ["image-1"],
            [],
            1,
            "image",
        ),
        (
            None,
            [],
            [],
            None,
            "unknown",
        ),
    ],
)
def test_instagram_content_type_mapping(
    raw_type,
    image_urls,
    video_urls,
    carousel_count,
    expected,
):
    """Map Instagram media fields to unified content types."""

    result = normalize_instagram_content_type(
        raw_type,
        image_urls=image_urls,
        video_urls=video_urls,
        carousel_item_count=carousel_count,
    )

    assert result == expected


def test_instagram_media_extraction_merges_and_deduplicates():
    """Merge image and video lists without duplicate URLs."""

    raw_post = {
        "media": {
            "image_urls": [
                "image-1",
                "image-2",
            ],
            "video_urls": [
                "video-1",
                "image-1",
            ],
        },
    }

    assert extract_instagram_media_urls(
        raw_post
    ) == [
        "image-1",
        "image-2",
        "video-1",
    ]


@pytest.mark.parametrize(
    ("media_value", "expected"),
    [
        (None, []),
        ({}, []),
        ("invalid", []),
    ],
)
def test_instagram_media_extraction_handles_missing_data(
    media_value,
    expected,
):
    """Missing or invalid media objects produce an empty list."""

    assert extract_instagram_media_urls(
        {
            "media": media_value,
        }
    ) == expected