"""
Normalized Social Storage Mapping Tests

Verifies conversion from normalized connector metrics into MongoDB
social-post metrics without losing platform-specific meaning.
"""

from datetime import UTC, datetime

from app.schemas.normalized_social import (
    NormalizedSocialMetrics,
)
from app.services.normalized_social_storage_service import (
    map_normalized_metrics,
)


def test_facebook_reactions_mapping_preserves_semantics():
    """
    Facebook reactions must remain separate from likes.
    """

    normalized = NormalizedSocialMetrics(
        likes=None,
        reactions=74,
        comments=8,
        shares=5,
        views=0,
        captured_at=datetime.now(UTC),
    )

    stored = map_normalized_metrics(
        normalized,
    )

    assert stored.likes is None
    assert stored.reactions == 74
    assert stored.comments == 8
    assert stored.shares == 5

    # An observed zero is not missing data.
    assert stored.views == 0

    assert stored.captured_at is not None
    assert stored.captured_at.tzinfo == UTC


def test_instagram_likes_mapping_preserves_semantics():
    """
    Instagram likes must not be converted into reactions.
    """

    normalized = NormalizedSocialMetrics(
        likes=105,
        reactions=None,
        comments=4,
        shares=None,
        views=None,
        captured_at=datetime.now(UTC),
    )

    stored = map_normalized_metrics(
        normalized,
    )

    assert stored.likes == 105
    assert stored.reactions is None
    assert stored.comments == 4
    assert stored.shares is None
    assert stored.views is None


def test_all_supported_metrics_are_copied():
    """
    Map every supported normalized metric without data loss.
    """

    captured_at = datetime(
        2026,
        7,
        15,
        9,
        0,
        tzinfo=UTC,
    )

    normalized = NormalizedSocialMetrics(
        likes=10,
        reactions=20,
        comments=30,
        shares=40,
        saves=50,
        views=60,
        reach=70,
        impressions=80,
        captured_at=captured_at,
    )

    stored = map_normalized_metrics(
        normalized,
    )

    assert stored.model_dump() == {
        "likes": 10,
        "reactions": 20,
        "comments": 30,
        "shares": 40,
        "saves": 50,
        "views": 60,
        "reach": 70,
        "impressions": 80,
        "captured_at": captured_at,
    }


def test_naive_captured_at_is_interpreted_as_utc():
    """
    Compatibility behavior interprets naive observation times as UTC.
    """

    normalized = NormalizedSocialMetrics(
        likes=10,
        captured_at=datetime(
            2026,
            7,
            15,
            9,
            0,
        ),
    )

    stored = map_normalized_metrics(
        normalized,
    )

    assert stored.captured_at is not None
    assert stored.captured_at.tzinfo == UTC

    assert stored.captured_at == datetime(
        2026,
        7,
        15,
        9,
        0,
        tzinfo=UTC,
    )
