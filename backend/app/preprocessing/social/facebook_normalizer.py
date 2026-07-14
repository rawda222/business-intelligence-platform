"""
Facebook Social Data Normalizer

Converts the normalized Facebook collector output into
platform-independent application contracts.

Expected Facebook post fields include:

- id
- url
- text
- created_at
- type
- reactions_count
- comments_count
- shares_count
- views_count
- image_url
- video_url
- comments

The normalizer does not trust tenant identifiers from external data.
business_id and social_account_id are supplied by the secured
collection workflow.
"""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.schemas.normalized_social import (
    ContentType,
    InformationQuality,
    NormalizedSocialComment,
    NormalizedSocialMetrics,
    NormalizedSocialPost,
)


# ============================================================
# Date Parsing
# ============================================================
def parse_facebook_datetime(
    value: object,
) -> datetime | None:
    """
    Parse a Facebook ISO-8601 datetime as UTC.

    Invalid or missing values return None instead of failing the
    complete collection run.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


# ============================================================
# Numeric Parsing
# ============================================================
def parse_non_negative_integer(
    value: object,
) -> int | None:
    """
    Parse a non-negative integer.

    Facebook comment likes may arrive as strings such as "0".
    Missing, invalid, boolean, or negative values return None.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return None

    return parsed

def get_first_present_value(
    data: dict[str, Any],
    *keys: str,
) -> object:
    """
    Return the first present non-None value.

    Unlike the `or` operator, this helper preserves valid falsy
    values such as numeric zero.
    """

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return None

# ============================================================
# Text Helpers
# ============================================================
def normalize_text(
    value: object,
) -> str | None:
    """Strip text and convert empty values to None."""

    if not isinstance(value, str):
        return None

    normalized = value.strip()

    return normalized or None


def is_emoji_only_text(
    text: str,
) -> bool:
    """
    Return True when text has no letters or digits.

    This is intentionally a lightweight structural classifier.
    It does not perform sentiment analysis.
    """

    return not any(
        character.isalpha() or character.isdigit()
        for character in text
    )


def infer_comment_information_quality(
    text: str,
) -> InformationQuality:
    """
    Estimate structural information richness for a comment.

    High:
        Contains a question or sufficiently detailed words.

    Medium:
        Contains a short but meaningful textual reaction.

    Low:
        Emoji-only, punctuation-only, or extremely short text.

    This is not sentiment classification and does not determine
    whether a comment is positive or negative.
    """

    normalized = text.strip()

    if not normalized:
        return "low"

    if is_emoji_only_text(normalized):
        return "low"

    words = re.findall(
        r"\w+",
        normalized,
        flags=re.UNICODE,
    )

    if "?" in normalized or "؟" in normalized:
        return "high"

    if len(words) >= 5:
        return "high"

    if len(words) >= 2:
        return "medium"

    return "low"


# ============================================================
# Content-Type Mapping
# ============================================================
def normalize_facebook_content_type(
    raw_type: object,
    *,
    image_url: object = None,
    video_url: object = None,
    external_url: object = None,
) -> ContentType:
    """
    Map Facebook content information to a shared content type.
    """

    if isinstance(raw_type, str):
        normalized_type = raw_type.strip().lower()

        type_mapping: dict[str, ContentType] = {
            "text": "text",
            "photo": "image",
            "image": "image",
            "video": "video",
            "reel": "reel",
            "link": "link",
            "live": "live",
        }

        if normalized_type in type_mapping:
            return type_mapping[normalized_type]

    if normalize_text(video_url):
        return "video"

    if normalize_text(image_url):
        return "image"

    if normalize_text(external_url):
        return "link"

    return "text"


# ============================================================
# Media Extraction
# ============================================================
def extract_facebook_media_urls(
    raw_post: dict[str, Any],
) -> list[NormalizedSocialComment]:
    """
    Extract and deduplicate post-level media URLs.
    """

    values = [
        raw_post.get("image_url"),
        raw_post.get("video_url"),
    ]

    media_urls: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = normalize_text(value)

        if normalized is None or normalized in seen:
            continue

        seen.add(normalized)
        media_urls.append(normalized)

    return media_urls


# ============================================================
# Minimized Raw Payloads
# ============================================================
def build_minimized_post_raw_data(
    raw_post: dict[str, Any],
) -> dict[str, Any]:
    """
    Keep traceability fields without duplicating nested comments
    or unnecessarily large platform payloads.
    """

    return {
        "source_platform": "facebook",
        "source_post_id": raw_post.get("id"),
        "source_post_url": raw_post.get("url"),
        "raw_type": raw_post.get("type"),
        "image_url": raw_post.get("image_url"),
        "video_url": raw_post.get("video_url"),
        "external_url": raw_post.get("external_url"),
    }


def build_minimized_comment_raw_data(
    raw_comment: dict[str, Any],
) -> dict[str, Any]:
    """
    Keep minimal comment traceability data.

    Full author profiles, profile pictures, gender, work
    information, and similar unnecessary personal data are not
    copied into the normalized contract.
    """

    return {
        "source_platform": "facebook",
        "source_comment_id": raw_comment.get("id"),
        "post_url": raw_comment.get("post_url"),
    }


# ============================================================
# Comment Normalization
# ============================================================
def normalize_facebook_comment(
    raw_comment: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    platform_post_id: str,
    connector_type: str,
) -> NormalizedSocialComment | None:
    """
    Normalize one Facebook comment.

    Empty comments are skipped.
    """

    text = normalize_text(raw_comment.get("text"))

    if text is None:
        return None

    author = raw_comment.get("author")

    author_reference = None

    if isinstance(author, dict):
        author_reference = (
            normalize_text(author.get("id"))
            or normalize_text(author.get("name"))
        )

    comment_id = (
        normalize_text(raw_comment.get("id"))
        or normalize_text(raw_comment.get("comment_id"))
    )

    emoji_only = is_emoji_only_text(text)

    return NormalizedSocialComment(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="facebook",
        platform_post_id=platform_post_id,
        platform_comment_id=comment_id,
        text=text,
        published_at=parse_facebook_datetime(
            raw_comment.get("created_at")
            or raw_comment.get("date")
        ),
        like_count=parse_non_negative_integer(
            get_first_present_value(
                raw_comment,
                "likes_count",
                "likesCount",
            )
        ),
        reply_count=parse_non_negative_integer(
            raw_comment.get("reply_count")
        ),
        author_reference=author_reference,
        information_quality=(
            infer_comment_information_quality(text)
        ),
        is_emoji_only=emoji_only,
        connector_type=connector_type,
        raw_data=build_minimized_comment_raw_data(
            raw_comment
        ),
    )


def normalize_facebook_comments(
    raw_post: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    platform_post_id: str,
    connector_type: str,
) -> list[NormalizedSocialComment]:
    """
    Normalize all usable comments attached to one post.
    """

    raw_comments = raw_post.get("comments")

    if not isinstance(raw_comments, list):
        return []

    normalized_comments: list[NormalizedSocialComment] = []

    for raw_comment in raw_comments:
        if not isinstance(raw_comment, dict):
            continue

        normalized = normalize_facebook_comment(
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
def normalize_facebook_post(
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
    Normalize one Facebook post and its attached comments.

    Raises:
        ValueError:
            When the post has no usable external ID.
    """

    platform_post_id = normalize_text(
        raw_post.get("id")
    )

    if platform_post_id is None:
        raise ValueError(
            "Facebook post is missing a usable id."
        )

    normalized_collected_at = (
        parse_facebook_datetime(collected_at)
    )

    if normalized_collected_at is None:
        raise ValueError(
            "collected_at must be a valid datetime."
        )

    normalized_connector_type = connector_type.strip().lower()

    if not normalized_connector_type:
        raise ValueError(
            "connector_type must not be empty."
        )

    media_urls = extract_facebook_media_urls(
        raw_post
    )

    content_type = normalize_facebook_content_type(
        raw_post.get("type"),
        image_url=raw_post.get("image_url"),
        video_url=raw_post.get("video_url"),
        external_url=raw_post.get("external_url"),
    )

    comments_count = parse_non_negative_integer(
        raw_post.get("comments_count")
    )

    normalized_post = NormalizedSocialPost(
        business_id=business_id,
        social_account_id=social_account_id,
        platform="facebook",
        platform_post_id=platform_post_id,
        published_at=parse_facebook_datetime(
            raw_post.get("created_at")
        ),
        text=normalize_text(raw_post.get("text")),
        content_type=content_type,
        post_url=normalize_text(raw_post.get("url")),
        hashtags=[],
        mentions=[],
        tagged_accounts=[],
        media_urls=media_urls,
        language=None,
        location_name=None,
        is_pinned=None,
        metrics=NormalizedSocialMetrics(
            likes=None,
            reactions=parse_non_negative_integer(
                raw_post.get("reactions_count")
            ),
            comments=comments_count,
            shares=parse_non_negative_integer(
                raw_post.get("shares_count")
            ),
            saves=None,
            views=parse_non_negative_integer(
                raw_post.get("views_count")
            ),
            reach=None,
            impressions=None,
            captured_at=normalized_collected_at,
        ),
        connector_type=normalized_connector_type,
        raw_data=build_minimized_post_raw_data(
            raw_post
        ),
    )

    normalized_comments = normalize_facebook_comments(
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
def normalize_facebook_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    connector_type: str = "apify",
) -> tuple[
    list[NormalizedSocialPost],
    list[NormalizedSocialComment],
]:
    """
    Normalize the complete Facebook collector payload.

    Invalid post objects are skipped so one malformed post does not
    discard the complete collection run.
    """

    source = payload.get("source")

    collected_at_value = None

    if isinstance(source, dict):
        collected_at_value = source.get(
            "collected_at"
        )

    collected_at = parse_facebook_datetime(
        collected_at_value
    )

    if collected_at is None:
        collected_at = datetime.now(UTC)

    raw_posts = payload.get("posts")

    if not isinstance(raw_posts, list):
        return [], []

    normalized_posts: list[NormalizedSocialPost] = []
    normalized_comments: list[NormalizedSocialComment] = []

    for raw_post in raw_posts:
        if not isinstance(raw_post, dict):
            continue

        try:
            post, comments = normalize_facebook_post(
                raw_post,
                business_id=business_id,
                social_account_id=social_account_id,
                collected_at=collected_at,
                connector_type=connector_type,
            )
        except ValueError:
            continue

        normalized_posts.append(post)
        normalized_comments.extend(comments)

    return normalized_posts, normalized_comments