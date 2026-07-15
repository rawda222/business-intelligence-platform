"""
Social Payload Processing Service

Coordinates platform-specific normalization with normalized social
post batch storage and normalized social comment batch storage.

Current behavior:

- Facebook raw payloads are normalized. Posts and comments are
  persisted to MongoDB.
- Instagram raw payloads are normalized. Posts and comments are
  persisted to MongoDB.
- Storage failures follow the batch continue_on_error policy.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.preprocessing.social.facebook_normalizer import (
    normalize_facebook_payload,
)
from app.preprocessing.social.instagram_normalizer import (
    normalize_instagram_payload,
)
from app.schemas.normalized_social import (
    NormalizedSocialComment,
    NormalizedSocialPost,
)
from app.services.normalized_social_storage_service import (
    NormalizedSocialBatchStorageResult,
    store_normalized_social_posts,
)
from app.services.social_comment_storage_service import (
    SocialCommentBatchStorageResult,
    store_normalized_social_comments,
)


# ============================================================
# Processing Result
# ============================================================
@dataclass(slots=True)
class SocialPayloadProcessingResult:
    """
    Result returned after normalizing and storing one raw payload.

    platform:
        Platform whose payload was processed.

    normalized_posts:
        Valid posts produced by the platform normalizer.

    normalized_comments:
        Valid comments produced by the platform normalizer.

    storage:
        Batch storage summary for normalized posts.

    comment_storage:
        Batch storage summary for normalized comments.
    """

    platform: Literal[
        "facebook",
        "instagram",
    ]

    normalized_posts: list[
        NormalizedSocialPost
    ]

    normalized_comments: list[
        NormalizedSocialComment
    ]

    storage: NormalizedSocialBatchStorageResult

    comment_storage: SocialCommentBatchStorageResult

    @property
    def posts_normalized(self) -> int:
        """Return the number of valid normalized posts."""

        return len(
            self.normalized_posts
        )

    @property
    def comments_normalized(self) -> int:
        """Return the number of valid normalized comments."""

        return len(
            self.normalized_comments
        )

    @property
    def comments_persisted(self) -> int:
        """
        Return the number of comments successfully persisted.

        This includes newly created, updated, and unchanged existing
        comments because each successful result resolves to a
        persisted MongoDB comment document.
        """

        return (
            self.comment_storage
            .comments_succeeded
        )


# ============================================================
# Facebook Payload Processing
# ============================================================
async def process_facebook_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    connector_type: str = "apify",
    collection_run_id: UUID | None = None,
    continue_on_error: bool = True,
) -> SocialPayloadProcessingResult:
    """
    Normalize and store one complete Facebook collector payload.

    Invalid Facebook post records are skipped by the normalizer.
    Valid normalized posts and comments are persisted through their
    respective batch storage services.
    """

    normalized_posts, normalized_comments = (
        normalize_facebook_payload(
            payload,
            business_id=business_id,
            social_account_id=social_account_id,
            connector_type=connector_type,
        )
    )

    storage_result = (
        await store_normalized_social_posts(
            normalized_posts,
            collection_run_id=collection_run_id,
            continue_on_error=continue_on_error,
        )
    )

    comment_storage_result = (
        await store_normalized_social_comments(
            normalized_comments,
            continue_on_error=continue_on_error,
        )
    )

    return SocialPayloadProcessingResult(
        platform="facebook",
        normalized_posts=normalized_posts,
        normalized_comments=normalized_comments,
        storage=storage_result,
        comment_storage=comment_storage_result,
    )


# ============================================================
# Instagram Payload Processing
# ============================================================
async def process_instagram_payload(
    payload: dict[str, Any],
    *,
    business_id: UUID,
    social_account_id: UUID,
    connector_type: str = "apify",
    collected_at: datetime | None = None,
    collection_run_id: UUID | None = None,
    continue_on_error: bool = True,
) -> SocialPayloadProcessingResult:
    """
    Normalize and store one complete Instagram collector payload.

    An explicit collected_at has priority over profile.scraped_at,
    following the Instagram normalizer policy.

    Valid normalized posts and comments are persisted through their
    respective batch storage services.
    """

    normalized_posts, normalized_comments = (
        normalize_instagram_payload(
            payload,
            business_id=business_id,
            social_account_id=social_account_id,
            connector_type=connector_type,
            collected_at=collected_at,
        )
    )

    storage_result = (
        await store_normalized_social_posts(
            normalized_posts,
            collection_run_id=collection_run_id,
            continue_on_error=continue_on_error,
        )
    )

    comment_storage_result = (
        await store_normalized_social_comments(
            normalized_comments,
            continue_on_error=continue_on_error,
        )
    )

    return SocialPayloadProcessingResult(
        platform="instagram",
        normalized_posts=normalized_posts,
        normalized_comments=normalized_comments,
        storage=storage_result,
        comment_storage=comment_storage_result,
    )