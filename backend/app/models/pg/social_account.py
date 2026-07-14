"""
Social Account Model

Represents a social media account connected to a business.

A single business can connect multiple social accounts, including
multiple accounts on the same platform.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


if TYPE_CHECKING:
    from app.models.pg.business import Business


class SocialAccount(Base):
    """
    A social media account connected to a business.

    One business may connect multiple social accounts, including
    multiple accounts on the same platform.
    """

    __tablename__ = "social_accounts"

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_account_id",
            name="uq_social_accounts_platform_account",
        ),
        Index(
            "ix_social_accounts_business_platform",
            "business_id",
            "platform",
        ),
    )

    # ========================================================
    # Primary Key
    # ========================================================
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # ========================================================
    # Business / Tenant
    # ========================================================
    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ========================================================
    # Platform Identity
    # ========================================================
    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    platform_account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    account_username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    account_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # ========================================================
    # Data Connector
    # ========================================================
    connector_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="apify",
    )

    credential_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # ========================================================
    # Flexible Platform Metadata
    # ========================================================
    account_metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # ========================================================
    # Status
    # ========================================================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    connection_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    # ========================================================
    # Timestamps
    # ========================================================
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ========================================================
    # Relationships
    # ========================================================
    business: Mapped["Business"] = relationship(
        "Business",
        back_populates="social_accounts",
    )

    def __repr__(self) -> str:
        return (
            f"<SocialAccount "
            f"{self.platform}:{self.platform_account_id}>"
        )