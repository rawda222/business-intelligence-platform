"""
Connected Social Platform Adapter

Converts PostgreSQL SocialAccount records into a minimized,
tenant-scoped list of platforms usable by automatic creative
context generation.

A usable account must:

- Belong to the requested business.
- Be active.
- Have connection_status set to connected.
- Contain a non-empty platform identifier.

The adapter does not query the database and does not inspect
credentials or connector secrets.
"""

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from app.creative_context.exceptions import (
    SocialPlatformContextError,
)
from app.models.pg.social_account import (
    SocialAccount,
)


@dataclass(frozen=True, slots=True)
class ConnectedSocialPlatformContext:
    """Usable connected platforms with operational warnings."""

    platforms: tuple[str, ...]

    usable_account_ids: tuple[UUID, ...]

    warnings: tuple[str, ...]


def _normalize_platform(
    value: str,
) -> str:
    """Normalize one social-platform identifier."""

    return value.strip().lower()


def extract_connected_social_platforms(
    *,
    accounts: Sequence[SocialAccount],
    business_id: UUID,
) -> ConnectedSocialPlatformContext:
    """
    Extract active, connected platforms for one business.

    Cross-business records are rejected instead of silently ignored
    to preserve tenant isolation at the adapter boundary.
    """

    platforms: list[str] = []

    usable_account_ids: list[UUID] = []

    warnings: list[str] = []

    for account in accounts:
        if account.business_id != business_id:
            raise SocialPlatformContextError(
                "Social account does not belong "
                "to the requested business."
            )

        if not account.is_active:
            continue

        connection_status = (
            account.connection_status
            .strip()
            .lower()
        )

        if connection_status != "connected":
            continue

        platform = _normalize_platform(
            account.platform
        )

        if not platform:
            warnings.append(
                "A connected social account "
                "has an empty platform value "
                "and was ignored."
            )
            continue

        if platform not in platforms:
            platforms.append(
                platform
            )

        if account.id not in usable_account_ids:
            usable_account_ids.append(
                account.id
            )

    platforms.sort(
        key=str.casefold
    )

    if not platforms:
        warnings.append(
            "No active connected social "
            "account was available."
        )

    return ConnectedSocialPlatformContext(
        platforms=tuple(
            platforms
        ),
        usable_account_ids=tuple(
            usable_account_ids
        ),
        warnings=tuple(
            warnings
        ),
    )