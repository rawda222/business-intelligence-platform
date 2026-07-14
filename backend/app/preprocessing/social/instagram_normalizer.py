"""
Instagram Social Data Normalizer

Converts Instagram collector output into platform-independent
application contracts.

Expected Instagram post fields include:

- shortcode
- url
- caption
- posted_at
- likes
- comments_count
- media
    - media_type
    - image_urls
    - video_urls
    - carousel_item_count
- hashtags
- mentions
- tagged_accounts
- location_name
- is_pinned
- comments_sampled
- sample_comments

The normalizer does not trust tenant identifiers from external data.
business_id and social_account_id are supplied by the secured
collection workflow.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.preprocessing.social.common import (
    build_minimized_raw_data,
    get_first_present_value,
    infer_information_quality,
    is_emoji_only_text,
    merge_string_lists,
    normalize_connector_type,
    normalize_external_identifier,
    normalize_string_list,
    normalize_text,
    parse_datetime_utc,
    parse_non_negative_integer,
)
from app.schemas.normalized_social import (
    ContentType,
    NormalizedSocialComment,
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)


# ============================================================
# Content-Type Mapping
# ============================================================
def normalize_instagram_content_type(
    raw_media_type: object,
    *,
    image_urls: object = None,
    video_urls: object = None,
    carousel_item_count: object = None,
) -> ContentType:
    """
    Map Instagram media information to the shared content types.

    The collector may return values such as:
    - image
    - video
    - carousel
    - reel

    When media_type is missing, available media fields are used
    as a fallback.
    """

    if isinstance(raw_media_type, str):
        normalized_type = raw_media_type.strip().lower()

        type_mapping: dict[str, ContentType] = {
            "image": "image",
            "photo": "image",
            "video": "video",
            "carousel": "carousel",
            "sidecar": "carousel",
            "reel": "reel",
            "clips": "reel",
            "text": "text",
        }

        if normalized_type in type_mapping:
            return type_mapping[normalized_type]

    parsed_carousel_count = parse_non_negative_integer(
        carousel_item_count
    )

    if (
        parsed_carousel_count is not None
        and parsed_carousel_count > 1
    ):
        return "carousel"

    normalized_video_urls = normalize_string_list(
        video_urls
    )

    if normalized_video_urls:
        return "video"

    normalized_image_urls = normalize_string_list(
        image_urls
    )

    if len(normalized_image_urls) > 1:
        return "carousel"

    if normalized_image_urls:
        return "image"

    return "unknown"


# ============================================================
# Media Extraction
# ============================================================
def extract_instagram_media_urls(
    raw_post: dict[str, Any],
) -> list:
    """
    Merge image and video URLs from the Instagram media object.

    URLs are deduplicated while preserving source order.
    """

    media = raw_post.get("media")

    if not isinstance(media, dict):
        return []

    return merge_string_lists(
        media.get("image_urls"),
        media.get("video_urls"),
    )


# ============================================================
# Minimized Raw Payloads
# ============================================================
def build_minimized_instagram_post_raw_data(
    raw_post: dict[str, Any],
) -> dict[str, object]:
    """
    Keep post traceability and structural media information.

    Large media lists and nested sampled comments are already
    represented by normalized fields and are not duplicated here.
    """

    media = raw_post.get("media")

    media_type = None
    carousel_item_count = None

    if isinstance(media, dict):
        media_type = media.get("media_type")
        carousel_item_count = media.get(
            "carousel_item_count"
        )

    return build_minimized_raw_data(
        source_platform="instagram",
        allowed_fields={
            "source_post_id": raw_post.get("shortcode"),
            "source_post_url": raw_post.get("url"),
            "raw_media_type": media_type,
            "carousel_item_count": carousel_item_count,
            "comments_sampled": raw_post.get(
                "comments_sampled"
            ),
        },
    )


def build_minimized_instagram_comment_raw_data(
    raw_comment: dict[str, Any],
) -> dict[str, object]:
    """
    Keep minimal Instagram comment traceability data.

    Full author profiles or unrelated personal information are not
    copied into the normalized contract.
    """

    return build_minimized_raw_data(
        source_platform="instagram",
        allowed_fields={
            "source_comment_id": get_first_present_value(
                raw_comment,
                "id",
                "comment_id",
            ),
        },
    )


# ============================================================
# Comment Normalization
# ============================================================
def normalize_instagram_comment(
    raw_comment: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    platform_post_id: str,
    connector_type: str,
) -> NormalizedSocialComment | None:
    """
    Normalize one sampled Instagram comment.

    Empty comments are skipped.

    The collector sample may not contain a comment ID. In that case
    platform_comment_id remains None.
    """

    text = normalize_text(
        raw_comment.get("text")
    )

    if text is None:
        return None

    comment_id = normalize_external_identifier(
        get_first_present_value(
            raw_comment,
            "id",
            "comment_id",
        )
    )

    author_reference = normalize_external_identifier(
        get_first_present_value(
            raw_comment,
            "author_username",
            "username",
            "author_id",
        )
    )

    published_at = parse_datetime_utc(
        get_first_present_value(
            raw_comment,
            "posted_at",
            "created_at",
            "date",
        )
    )

    like_count = parse_non_negative_integer(
        get_first_present_value(
            raw_comment,
            "like_count",
            "likes_count",
            "likesCount",
        )
    )

    reply_count = parse_non_negative_integer(
        get_first_present_value(
            raw_comment,
            "reply_count",
            "replies_count",
        )
    )

    emoji_only = is_emoji_only_text(text)

    return NormalizedSocialComment(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="instagram",
        platform_post_id=platform_post_id,
        platform_comment_id=comment_id,
        text=text,
        published_at=published_at,
        like_count=like_count,
        reply_count=reply_count,
        author_reference=author_reference,
        information_quality=(
            infer_information_quality(text)
        ),
        is_emoji_only=emoji_only,
        connector_type=connector_type,
        raw_data=(
            build_minimized_instagram_comment_raw_data(
                raw_comment
            )
        ),
    )


def normalize_instagram_comments(
    raw_post: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    platform_post_id: str,
    connector_type: str,
) -> list:
    """
    Normalize usable sampled comments attached to one post.

    comments_count remains the total count reported by Instagram.
    sample_comments represents only the available collected sample.
    """

    raw_comments = raw_post.get(
        "sample_comments"
    )

    if not isinstance(raw_comments, list):
        return []

    normalized_comments: list[
        NormalizedSocialComment
    ] = []

    for raw_comment in raw_comments:
        if not isinstance(raw_comment, dict):
            continue

        normalized = normalize_instagram_comment(
            raw_comment,
            business_id=business_id,
            social_account_id=social_account_id,
            platform_post_id=platform_post_id,
            connector_type=connector_type,
        )

        if normalized is not None:
            normalized_comments.append(normalized)

    return normalized_comments


# ============================================================
# Post Normalization
# ============================================================
def normalize_instagram_post(
    raw_post: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    collected_at: datetime,
    connector_type: str = "apify",
) -> tuple[
    NormalizedSocialPost,
    list[NormalizedSocialComment],
]:
    """
    Normalize one Instagram post and its sampled comments.

    Raises:
        ValueError:
            When the post has no usable shortcode.
    """

    platform_post_id = normalize_external_identifier(
        get_first_present_value(
            raw_post,
            "shortcode",
            "id",
        )
    )

    if platform_post_id is None:
        raise ValueError(
            "Instagram post is missing a usable shortcode."
        )

    normalized_collected_at = parse_datetime_utc(
        collected_at
    )

    if normalized_collected_at is None:
        raise ValueError(
            "collected_at must be a valid datetime."
        )

    normalized_connector_type = (
        normalize_connector_type(
            connector_type
        )
    )

    if normalized_connector_type is None:
        raise ValueError(
            "connector_type must not be empty."
        )

    media = raw_post.get("media")

    if not isinstance(media, dict):
        media = {}

    content_type = normalize_instagram_content_type(
        media.get("media_type"),
        image_urls=media.get("image_urls"),
        video_urls=media.get("video_urls"),
        carousel_item_count=media.get(
            "carousel_item_count"
        ),
    )

    media_urls = extract_instagram_media_urls(
        raw_post
    )

    hashtags = normalize_string_list(
        raw_post.get("hashtags"),
        remove_social_prefix=True,
    )

    mentions = normalize_string_list(
        raw_post.get("mentions"),
        remove_social_prefix=True,
    )

    tagged_accounts = normalize_string_list(
        raw_post.get("tagged_accounts"),
        remove_social_prefix=True,
    )

    normalized_post = NormalizedSocialPost(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="instagram",
        platform_post_id=platform_post_id,
        published_at=parse_datetime_utc(
            raw_post.get("posted_at")
        ),
        text=normalize_text(
            raw_post.get("caption")
        ),
        content_type=content_type,
        post_url=normalize_text(
            raw_post.get("url")
        ),
        hashtags=hashtags,
        mentions=mentions,
        tagged_accounts=tagged_accounts,
        media_urls=media_urls,
        language=None,
        location_name=normalize_text(
            raw_post.get("location_name")
        ),
        is_pinned=(
            raw_post.get("is_pinned")
            if isinstance(
                raw_post.get("is_pinned"),
                bool,
            )
            else None
        ),
        metrics=NormalizedSocialMetrics(
            likes=parse_non_negative_integer(
                raw_post.get("likes")
            ),
            reactions=None,
            comments=parse_non_negative_integer(
                raw_post.get("comments_count")
            ),
            shares=None,
            saves=None,
            views=parse_non_negative_integer(
                get_first_present_value(
                    raw_post,
                    "views",
                    "views_count",
                    "video_view_count",
                )
            ),
            reach=None,
            impressions=None,
            captured_at=normalized_collected_at,
        ),
        connector_type=normalized_connector_type,
        raw_data=(
            build_minimized_instagram_post_raw_data(
                raw_post
            )
        ),
    )

    normalized_comments = normalize_instagram_comments(
        raw_post,
        business_id=business_id,
        social_account_id=social_account_id,
        platform_post_id=platform_post_id,
        connector_type=normalized_connector_type,
    )

    return normalized_post, normalized_comments


# ============================================================
# Collector-Payload Normalization
# ============================================================
def normalize_instagram_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    connector_type: str = "apify",
    collected_at: datetime | None = None,
) -> tuple[
    list[NormalizedSocialPost],
    list[NormalizedSocialComment],
]:
    """
    Normalize a complete Instagram collector payload.

    The supplied collected_at has priority. If it is missing, the
    profile-level scraped_at value is used. If neither is valid,
    the current UTC time is used.

    Invalid post objects are skipped so one malformed record does not
    discard the complete collection run.
    """

    normalized_collected_at = parse_datetime_utc(
        collected_at
    )

    if normalized_collected_at is None:
        profile = payload.get("profile")

        scraped_at = None

        if isinstance(profile, dict):
            scraped_at = profile.get(
                "scraped_at"
            )

        normalized_collected_at = (
            parse_datetime_utc(scraped_at)
        )

    if normalized_collected_at is None:
        normalized_collected_at = datetime.now(
            UTC
        )

    raw_posts = payload.get("posts")

    if not isinstance(raw_posts, list):
        return [], []

    normalized_posts: list[
        NormalizedSocialPost
    ] = []

    normalized_comments: list[
        NormalizedSocialComment
    ] = []

    for raw_post in raw_posts:
        if not isinstance(raw_post, dict):
            continue

        try:
            post, comments = normalize_instagram_post(
                raw_post,
                business_id=business_id,
                social_account_id=social_account_id,
                collected_at=normalized_collected_at,
                connector_type=connector_type,
            )
        except ValueError:
            continue

        normalized_posts.append(post)
        normalized_comments.extend(comments)

    return normalized_posts, normalized_comments