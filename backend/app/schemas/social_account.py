"""
Social Account Schemas

Pydantic schemas for creating, updating, and returning
social media accounts connected to businesses.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


# ============================================================
# Supported Values
# ============================================================
ConnectionStatus = Literal[
    "pending",
    "connected",
    "disconnected",
    "error",
    "reauthorization_required",
]


# ============================================================
# Base Social Account Schema
# ============================================================
class SocialAccountBase(BaseSchema):
    """
    Shared public fields for social account schemas.

    business_id is intentionally excluded because it comes from
    the secured API route:

    /businesses/{business_id}/social-accounts
    """

    platform: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,49}$",
        examples=["facebook", "instagram", "linkedin"],
    )

    platform_account_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    account_username: str | None = Field(
        default=None,
        max_length=255,
    )

    account_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    connector_type: str = Field(
        default="apify",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,49}$",
        examples=["apify", "official_api", "manual_import"],
    )

    account_metadata: dict = Field(
        default_factory=dict,
    )

    @field_validator("platform", "connector_type", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        """
        Normalize platform and connector identifiers.

        Examples:
        Instagram    -> instagram
        OFFICIAL_API -> official_api
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value


# ============================================================
# Input: Create Social Account
# ============================================================
class SocialAccountCreate(SocialAccountBase):
    """
    Schema for connecting a social media account to a business.

    Server-controlled fields are not accepted:
    - business_id
    - credential_reference
    - connection_status
    - connected_at
    - is_active
    - created_at
    - updated_at
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


# ============================================================
# Input: Update Social Account
# ============================================================
class SocialAccountUpdate(BaseSchema):
    """
    Schema for partially updating a connected social account.

    Platform identity fields are immutable:
    - platform
    - platform_account_id

    A different platform identity must be connected as a new
    social account instead of modifying an existing identity.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    account_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    account_username: str | None = Field(
        default=None,
        max_length=255,
    )

    account_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    connector_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,49}$",
    )

    account_metadata: dict | None = None

    is_active: bool | None = None

    @field_validator("connector_type", mode="before")
    @classmethod
    def normalize_connector_type(cls, value: object) -> object:
        """Normalize the connector identifier before validation."""

        if isinstance(value, str):
            return value.strip().lower()

        return value


# ============================================================
# Output: Social Account Response
# ============================================================
class SocialAccountResponse(
    SocialAccountBase,
    IDSchema,
    TimestampSchema,
):
    """
    Full public representation of a connected social account.

    Credential references and secrets are never returned.
    """

    business_id: UUID

    is_active: bool

    connection_status: ConnectionStatus

    connected_at: datetime | None = None


# ============================================================
# Output: Social Account Summary
# ============================================================
class SocialAccountSummary(IDSchema):
    """Lightweight representation used in account lists."""

    platform: str

    platform_account_id: str

    account_name: str

    account_username: str | None = None

    is_active: bool

    connection_status: ConnectionStatus