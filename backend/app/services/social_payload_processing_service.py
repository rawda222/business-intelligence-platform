"""
Social Payload Processing Service

Coordinates platform-specific normalization with normalized social
post batch storage.

Current behavior:

- Facebook raw payloads are normalized and their posts are stored.
- Instagram raw payloads are normalized and their posts are stored.
- Normalized comments are returned to the caller but are not yet
  persisted because SocialCommentDocument has not been introduced.
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

        Comments are returned for later analysis or persistence.
        They are not yet stored in MongoDB.

    storage:
        Batch storage summary for normalized posts.
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
        Return persisted comment count.

        Comment persistence is intentionally not implemented yet.
        """

        return 0


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
    Valid normalized posts are sent through normalized batch storage.

    Normalized comments are returned but not persisted.
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

    return SocialPayloadProcessingResult(
        platform="facebook",
        normalized_posts=normalized_posts,
        normalized_comments=normalized_comments,
        storage=storage_result,
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

    Normalized comments are returned but not persisted.
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

    return SocialPayloadProcessingResult(
        platform="instagram",
        normalized_posts=normalized_posts,
        normalized_comments=normalized_comments,
        storage=storage_result,
    )