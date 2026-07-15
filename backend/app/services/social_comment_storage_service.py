"""
Social Comment Storage Service

Coordinates normalized social-comment identity and persistence.

Current responsibilities:

- Build deterministic comment deduplication keys.
- Preserve platform comment identity when available.
- Build stable SHA-256 keys when an external ID is unavailable.
- Find the parent social post inside the exact tenant scope.

Comment create, update, and batch persistence are added after these
identity rules are verified independently.
"""

import hashlib
import json

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.mongo.social_comment import (
    SocialCommentDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
)
from app.schemas.normalized_social import (
    NormalizedSocialComment,
)
from app.services.post_metric_service import (
    ensure_utc,
)


# ============================================================
# Comment Identity
# ============================================================
def build_comment_deduplication_key(
    comment: NormalizedSocialComment,
) -> str:
    """
    Build a stable deduplication key for one normalized comment.

    When platform_comment_id is available, it is the strongest
    identity supplied by the external platform.

    Very long external IDs are converted into a SHA-256 key so the
    result always fits the SocialCommentDocument field limit.

    When no external comment ID is available, the key is generated
    from a canonical representation of:

    - business_id
    - social_account_id
    - platform
    - platform_post_id
    - author_reference
    - published_at
    - comment text

    Python hash() is intentionally not used because its output is not
    guaranteed to remain stable across different Python processes.
    """

    platform_comment_id = (
        comment.platform_comment_id.strip()
        if comment.platform_comment_id is not None
        else ""
    )

    if platform_comment_id:
        readable_key = (
            f"id:{platform_comment_id}"
        )

        if len(readable_key) <= 128:
            return readable_key

        external_id_digest = hashlib.sha256(
            platform_comment_id.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            f"id-sha256:{external_id_digest}"
        )

    published_at = (
        ensure_utc(
            comment.published_at
        ).isoformat()
        if comment.published_at is not None
        else ""
    )

    canonical_identity = {
        "business_id": str(
            comment.business_id
        ),
        "social_account_id": str(
            comment.social_account_id
        ),
        "platform": comment.platform,
        "platform_post_id": (
            comment.platform_post_id
        ),
        "author_reference": (
            comment.author_reference
            or ""
        ),
        "published_at": published_at,
        "text": comment.text,
    }

    serialized_identity = json.dumps(
        canonical_identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    digest = hashlib.sha256(
        serialized_identity.encode(
            "utf-8"
        )
    ).hexdigest()

    return f"sha256:{digest}"


# ============================================================
# Parent Post Lookup
# ============================================================
async def find_comment_parent_post(
    comment: NormalizedSocialComment,
) -> SocialPostDocument | None:
    """
    Find the comment's parent post inside the exact tenant scope.

    Matching requires:

    - business_id
    - social_account_id
    - platform
    - platform_post_id

    A platform post identifier alone is never treated as globally
    unique across businesses or connected social accounts.
    """

    return await SocialPostDocument.find_one(
        SocialPostDocument.business_id
        == comment.business_id,
        SocialPostDocument.social_account_id
        == comment.social_account_id,
        SocialPostDocument.platform
        == comment.platform,
        SocialPostDocument.platform_post_id
        == comment.platform_post_id,
    )

# ============================================================
# Storage Errors
# ============================================================
class SocialCommentParentNotFoundError(
    ValueError
):
    """
    Raised when the normalized comment's parent post is missing.
    """


# ============================================================
# Single Comment Storage Result
# ============================================================
@dataclass(slots=True)
class SocialCommentStorageResult:
    """
    Result returned after storing one normalized comment.

    comment:
        The persisted MongoDB comment document.

    created:
        True when a new comment document was inserted.

    updated:
        Reserved for safe-update behavior added in the next stage.

    reason:
        Machine-readable storage outcome.
    """

    comment: SocialCommentDocument

    created: bool

    updated: bool

    reason: str

    # ============================================================
# Existing Comment Lookup
# ============================================================
async def find_existing_comment(
    *,
    comment: NormalizedSocialComment,
    deduplication_key: str,
) -> SocialCommentDocument | None:
    """
    Find an existing comment inside the exact tenant scope.

    The lookup matches the same fields protected by the unique
    MongoDB index:

    - business_id
    - social_account_id
    - platform
    - deduplication_key
    """

    return await SocialCommentDocument.find_one(
        SocialCommentDocument.business_id
        == comment.business_id,
        SocialCommentDocument.social_account_id
        == comment.social_account_id,
        SocialCommentDocument.platform
        == comment.platform,
        SocialCommentDocument.deduplication_key
        == deduplication_key,
    )

# ============================================================
# Comment Creation
# ============================================================
async def create_social_comment(
    *,
    comment: NormalizedSocialComment,
    parent_post: SocialPostDocument,
    deduplication_key: str,
) -> SocialCommentDocument:
    """
    Create one MongoDB social-comment document.

    The supplied parent post must already have been resolved inside
    the comment's exact tenant scope.
    """

    if parent_post.id is None:
        raise ValueError(
            "Parent social post must be persisted "
            "before storing comments."
        )

    now = datetime.now(
        UTC,
    )

    normalized_published_at = (
        ensure_utc(
            comment.published_at
        )
        if comment.published_at is not None
        else None
    )

    normalized_platform_comment_id = (
        comment.platform_comment_id.strip()
        if (
            comment.platform_comment_id
            is not None
            and comment.platform_comment_id.strip()
        )
        else None
    )

    stored_comment = SocialCommentDocument(
        business_id=comment.business_id,
        social_account_id=(
            comment.social_account_id
        ),
        social_post_id=parent_post.id,
        platform=comment.platform,
        platform_post_id=(
            comment.platform_post_id
        ),
        platform_comment_id=(
            normalized_platform_comment_id
        ),
        deduplication_key=deduplication_key,
        text=comment.text,
        published_at=normalized_published_at,
        like_count=comment.like_count,
        reply_count=comment.reply_count,
        author_reference=(
            comment.author_reference
        ),
        information_quality=(
            comment.information_quality
        ),
        is_emoji_only=comment.is_emoji_only,
        connector_type=(
            comment.connector_type
        ),
        raw_data=dict(
            comment.raw_data
        ),
        collected_at=now,
        created_at=now,
        updated_at=now,
    )

    await stored_comment.insert()

    return stored_comment

    if existing_comment is not None:
        updated = await update_social_comment_safely(
            stored_comment=existing_comment,
            incoming_comment=comment,
        )

        if updated:
            refreshed_comment = (
                await SocialCommentDocument.get(
                    existing_comment.id
                )
            )

            if refreshed_comment is None:
                raise RuntimeError(
                    "Updated social comment could not "
                    "be reloaded."
                )

            return SocialCommentStorageResult(
                comment=refreshed_comment,
                created=False,
                updated=True,
                reason="comment_updated",
            )

        return SocialCommentStorageResult(
            comment=existing_comment,
            created=False,
            updated=False,
            reason="comment_already_exists",
        )

# ============================================================
# Safe Comment Update
# ============================================================
# ============================================================
# Safe Comment Update
# ============================================================
async def update_social_comment_safely(
    *,
    stored_comment: SocialCommentDocument,
    incoming_comment: NormalizedSocialComment,
) -> bool:
    """
    Safely update mutable comment fields.

    Missing optional incoming values preserve stored information.
    Zero values remain valid observations.

    Comment identity, tenant scope, deduplication key, and parent
    linkage are intentionally not modified.
    """

    changed = False

    # ========================================================
    # Comment Text
    # ========================================================
    if (
        incoming_comment.text is not None
        and stored_comment.text
        != incoming_comment.text
    ):
        stored_comment.text = (
            incoming_comment.text
        )

        changed = True

    # ========================================================
    # Published Time
    # ========================================================
    incoming_published_at = (
        ensure_utc(
            incoming_comment.published_at
        )
        if incoming_comment.published_at
        is not None
        else None
    )

    stored_published_at = (
        ensure_utc(
            stored_comment.published_at
        )
        if stored_comment.published_at
        is not None
        else None
    )

    if (
        incoming_published_at is not None
        and stored_published_at
        != incoming_published_at
    ):
        stored_comment.published_at = (
            incoming_published_at
        )

        changed = True

    # ========================================================
    # Observation Counts
    # ========================================================
    if (
        incoming_comment.like_count is not None
        and stored_comment.like_count
        != incoming_comment.like_count
    ):
        stored_comment.like_count = (
            incoming_comment.like_count
        )

        changed = True

    if (
        incoming_comment.reply_count is not None
        and stored_comment.reply_count
        != incoming_comment.reply_count
    ):
        stored_comment.reply_count = (
            incoming_comment.reply_count
        )

        changed = True

    # ========================================================
    # Optional Author Reference
    # ========================================================
    if (
        incoming_comment.author_reference
        is not None
        and stored_comment.author_reference
        != incoming_comment.author_reference
    ):
        stored_comment.author_reference = (
            incoming_comment.author_reference
        )

        changed = True

    # ========================================================
    # Classification Fields
    # ========================================================
    if (
        stored_comment.information_quality
        != incoming_comment.information_quality
    ):
        stored_comment.information_quality = (
            incoming_comment.information_quality
        )

        changed = True

    if (
        stored_comment.is_emoji_only
        != incoming_comment.is_emoji_only
    ):
        stored_comment.is_emoji_only = (
            incoming_comment.is_emoji_only
        )

        changed = True

    # ========================================================
    # Connector
    # ========================================================
    if (
        incoming_comment.connector_type
        is not None
        and stored_comment.connector_type
        != incoming_comment.connector_type
    ):
        stored_comment.connector_type = (
            incoming_comment.connector_type
        )

        changed = True

    # ========================================================
    # Minimized Raw Data Merge
    # ========================================================
    stored_raw_data = dict(
        stored_comment.raw_data
        or {}
    )

    merged_raw_data = dict(
        stored_raw_data
    )

    for key, value in (
        incoming_comment.raw_data.items()
    ):
        if value is None:
            continue

        merged_raw_data[key] = value

    if merged_raw_data != stored_raw_data:
        stored_comment.raw_data = (
            merged_raw_data
        )

        changed = True

    # ========================================================
    # No-Change Outcome
    # ========================================================
    if not changed:
        return False

    # ========================================================
    # Persist Changed Observation
    # ========================================================
    now = datetime.now(
        UTC,
    )

    stored_comment.collected_at = now
    stored_comment.updated_at = now

    await stored_comment.save()

    return True
# ============================================================
# Complete Single Comment Storage
# ============================================================
async def store_normalized_social_comment(
    comment: NormalizedSocialComment,
) -> SocialCommentStorageResult:
    """
    Store one normalized social comment idempotently.

    Existing comments are safely updated when mutable observations
    change. Identical observations return the existing document.
    """

    parent_post = await find_comment_parent_post(
        comment
    )

    if parent_post is None:
        raise SocialCommentParentNotFoundError(
            "Cannot store social comment because "
            "its tenant-scoped parent post was not found."
        )

    deduplication_key = (
        build_comment_deduplication_key(
            comment
        )
    )

    existing_comment = await find_existing_comment(
        comment=comment,
        deduplication_key=deduplication_key,
    )

    if existing_comment is not None:
        updated = await update_social_comment_safely(
            stored_comment=existing_comment,
            incoming_comment=comment,
        )

        if not updated:
            return SocialCommentStorageResult(
                comment=existing_comment,
                created=False,
                updated=False,
                reason="comment_already_exists",
            )

        if existing_comment.id is None:
            raise RuntimeError(
                "Updated social comment has no "
                "persisted document ID."
            )

        refreshed_comment = (
            await SocialCommentDocument.get(
                existing_comment.id
            )
        )

        if refreshed_comment is None:
            raise RuntimeError(
                "Updated social comment could not "
                "be reloaded."
            )

        return SocialCommentStorageResult(
            comment=refreshed_comment,
            created=False,
            updated=True,
            reason="comment_updated",
        )

    created_comment = await create_social_comment(
        comment=comment,
        parent_post=parent_post,
        deduplication_key=deduplication_key,
    )

    return SocialCommentStorageResult(
        comment=created_comment,
        created=True,
        updated=False,
        reason="comment_created",
    )
# ============================================================
# Batch Comment Storage Result
# ============================================================
@dataclass(slots=True)
class SocialCommentBatchStorageResult:
    """
    Summary returned after storing normalized social comments.
    """

    comments_received: int

    comments_succeeded: int

    comments_created: int

    comments_updated: int

    comments_unchanged: int

    failures: list[dict[str, str]]

    results: list[SocialCommentStorageResult]

# ============================================================
# Batch Comment Storage
# ============================================================
async def store_normalized_social_comments(
    comments: list[NormalizedSocialComment],
    *,
    continue_on_error: bool = True,
) -> SocialCommentBatchStorageResult:
    """
    Store multiple normalized social comments.

    When continue_on_error is True, one failed comment is recorded
    and processing continues for the remaining comments.

    When continue_on_error is False, the first exception is raised.
    """

    successful_results: list[
        SocialCommentStorageResult
    ] = []

    failures: list[dict[str, str]] = []

    comments_created = 0
    comments_updated = 0
    comments_unchanged = 0

    for comment in comments:
        try:
            result = (
                await store_normalized_social_comment(
                    comment
                )
            )
        except Exception as error:
            if not continue_on_error:
                raise

            failures.append(
                {
                    "platform": comment.platform,
                    "platform_post_id": (
                        comment.platform_post_id
                    ),
                    "platform_comment_id": (
                        comment.platform_comment_id
                        or ""
                    ),
                    "error_type": (
                        type(error).__name__
                    ),
                    "error_message": str(error),
                }
            )

            continue

        successful_results.append(
            result
        )

        if result.created:
            comments_created += 1
        elif result.updated:
            comments_updated += 1
        else:
            comments_unchanged += 1

    return SocialCommentBatchStorageResult(
        comments_received=len(comments),
        comments_succeeded=len(
            successful_results
        ),
        comments_created=comments_created,
        comments_updated=comments_updated,
        comments_unchanged=comments_unchanged,
        failures=failures,
        results=successful_results,
    )
