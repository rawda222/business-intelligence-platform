"""
Social Comment Identity Tests

Verifies deterministic comment deduplication keys without requiring
a MongoDB connection.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.schemas.normalized_social import (
    NormalizedSocialComment,
)
from app.services.social_comment_storage_service import (
    build_comment_deduplication_key,
)


BUSINESS_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

SOCIAL_ACCOUNT_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)


def build_test_comment(
    *,
    platform_comment_id: str | None,
    text: str = "الخدمة ممتازة",
    author_reference: str | None = "customer-1",
    published_at: datetime | None = None,
) -> NormalizedSocialComment:
    """
    Build one valid normalized comment for identity tests.
    """

    return NormalizedSocialComment(
        business_id=BUSINESS_ID,
        social_account_id=SOCIAL_ACCOUNT_ID,
        platform="facebook",
        platform_post_id="facebook-post-1",
        platform_comment_id=platform_comment_id,
        text=text,
        published_at=(
            published_at
            or datetime(
                2026,
                7,
                15,
                18,
                0,
                tzinfo=UTC,
            )
        ),
        like_count=0,
        reply_count=0,
        author_reference=author_reference,
        information_quality="high",
        is_emoji_only=False,
        connector_type="apify",
        raw_data={
            "source": "identity_test",
        },
    )


def test_external_comment_id_is_preferred():
    """
    Use a readable platform comment ID when one is available.
    """

    comment = build_test_comment(
        platform_comment_id="comment-123",
    )

    assert (
        build_comment_deduplication_key(
            comment
        )
        == "id:comment-123"
    )


def test_external_comment_id_is_trimmed():
    """
    Ignore surrounding whitespace in an external comment ID.
    """

    comment = build_test_comment(
        platform_comment_id=(
            "  comment-123  "
        ),
    )

    assert (
        build_comment_deduplication_key(
            comment
        )
        == "id:comment-123"
    )


def test_missing_external_id_generates_stable_sha256():
    """
    Generate the same fallback key for identical comment identity.
    """

    first = build_test_comment(
        platform_comment_id=None,
    )

    second = build_test_comment(
        platform_comment_id=None,
    )

    first_key = (
        build_comment_deduplication_key(
            first
        )
    )

    second_key = (
        build_comment_deduplication_key(
            second
        )
    )

    assert first_key == second_key

    assert first_key.startswith(
        "sha256:"
    )

    assert len(first_key) == (
        len("sha256:") + 64
    )


def test_fallback_identity_changes_when_text_changes():
    """
    Different comment text must create a different fallback key.
    """

    first = build_test_comment(
        platform_comment_id=None,
        text="الخدمة ممتازة",
    )

    changed = build_test_comment(
        platform_comment_id=None,
        text="الخدمة بطيئة",
    )

    assert (
        build_comment_deduplication_key(
            first
        )
        != build_comment_deduplication_key(
            changed
        )
    )


def test_fallback_identity_changes_when_author_changes():
    """
    Identical text from different authors must not be collapsed.
    """

    first = build_test_comment(
        platform_comment_id=None,
        author_reference="customer-1",
    )

    changed = build_test_comment(
        platform_comment_id=None,
        author_reference="customer-2",
    )

    assert (
        build_comment_deduplication_key(
            first
        )
        != build_comment_deduplication_key(
            changed
        )
    )


def test_fallback_identity_changes_when_time_changes():
    """
    Repeated text from the same author at another time is distinct.
    """

    first = build_test_comment(
        platform_comment_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
    )

    changed = build_test_comment(
        platform_comment_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            5,
            tzinfo=UTC,
        ),
    )

    assert (
        build_comment_deduplication_key(
            first
        )
        != build_comment_deduplication_key(
            changed
        )
    )


def test_fallback_identity_normalizes_datetime_to_utc():
    """
    Equivalent timestamps must produce the same fallback identity.

    Naive datetime values are interpreted as UTC according to the
    existing project compatibility policy.
    """

    aware_comment = build_test_comment(
        platform_comment_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
            tzinfo=UTC,
        ),
    )

    naive_comment = build_test_comment(
        platform_comment_id=None,
        published_at=datetime(
            2026,
            7,
            15,
            18,
            0,
        ),
    )

    assert (
        build_comment_deduplication_key(
            aware_comment
        )
        == build_comment_deduplication_key(
            naive_comment
        )
    )


def test_missing_author_and_time_remain_deterministic():
    """
    Missing optional identity fields still produce a stable key.
    """

    first = build_test_comment(
        platform_comment_id=None,
        author_reference=None,
        published_at=None,
    )

    second = build_test_comment(
        platform_comment_id=None,
        author_reference=None,
        published_at=None,
    )

    assert (
        build_comment_deduplication_key(
            first
        )
        == build_comment_deduplication_key(
            second
        )
    )


def test_very_long_external_id_is_hashed():
    """
    Keep generated keys inside the MongoDB model field limit.
    """

    comment = build_test_comment(
        platform_comment_id=(
            "x" * 300
        ),
    )

    key = build_comment_deduplication_key(
        comment
    )

    assert key.startswith(
        "id-sha256:"
    )

    assert len(key) == (
        len("id-sha256:") + 64
    )

    assert len(key) <= 128