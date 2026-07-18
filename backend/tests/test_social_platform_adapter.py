"""
Connected Social Platform Adapter Tests
"""

from uuid import UUID, uuid4

import pytest

from app.creative_context.exceptions import (
    SocialPlatformContextError,
)
from app.creative_context.social_platform_adapter import (
    extract_connected_social_platforms,
)
from app.models.pg.social_account import (
    SocialAccount,
)


_BUSINESS_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)


def _account(
    *,
    platform: str,
    is_active: bool = True,
    connection_status: str = "connected",
    business_id: UUID = _BUSINESS_ID,
) -> SocialAccount:
    """Build one in-memory social account."""

    return SocialAccount(
        id=uuid4(),
        business_id=business_id,
        platform=platform,
        platform_account_id=str(
            uuid4()
        ),
        account_name="Test Account",
        connector_type="apify",
        account_metadata={},
        is_active=is_active,
        connection_status=(
            connection_status
        ),
    )


def test_extracts_active_connected_platforms():
    """Active connected accounts should provide platforms."""

    result = extract_connected_social_platforms(
        accounts=[
            _account(
                platform=" Instagram ",
            ),
            _account(
                platform="facebook",
            ),
        ],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == (
        "facebook",
        "instagram",
    )

    assert len(
        result.usable_account_ids
    ) == 2

    assert result.warnings == ()


def test_pending_account_is_excluded():
    """Pending accounts are not operationally connected."""

    result = extract_connected_social_platforms(
        accounts=[
            _account(
                platform="instagram",
                connection_status="pending",
            ),
        ],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == ()

    assert result.warnings


def test_inactive_connected_account_is_excluded():
    """Inactive accounts should not drive automatic context."""

    result = extract_connected_social_platforms(
        accounts=[
            _account(
                platform="instagram",
                is_active=False,
            ),
        ],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == ()

    assert result.warnings


def test_duplicate_platforms_are_removed():
    """Multiple accounts may share one normalized platform."""

    result = extract_connected_social_platforms(
        accounts=[
            _account(
                platform="instagram",
            ),
            _account(
                platform="INSTAGRAM",
            ),
        ],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == (
        "instagram",
    )

    assert len(
        result.usable_account_ids
    ) == 2


def test_non_connected_statuses_are_excluded():
    """Unavailable account states should not be selected."""

    result = extract_connected_social_platforms(
        accounts=[
            _account(
                platform="instagram",
                connection_status=(
                    "disconnected"
                ),
            ),
            _account(
                platform="facebook",
                connection_status="error",
            ),
            _account(
                platform="linkedin",
                connection_status=(
                    "reauthorization_required"
                ),
            ),
        ],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == ()

    assert result.warnings


def test_cross_business_account_is_rejected():
    """An account from another tenant must fail explicitly."""

    with pytest.raises(
        SocialPlatformContextError,
        match="does not belong",
    ):
        extract_connected_social_platforms(
            accounts=[
                _account(
                    platform="instagram",
                    business_id=uuid4(),
                ),
            ],
            business_id=_BUSINESS_ID,
        )


def test_empty_account_list_returns_warning():
    """A business without accounts should produce safe fallback input."""

    result = extract_connected_social_platforms(
        accounts=[],
        business_id=_BUSINESS_ID,
    )

    assert result.platforms == ()

    assert result.usable_account_ids == ()

    assert (
        "No active connected"
        in result.warnings[0]
    )
