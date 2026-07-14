"""
Business Model

Represents a business owned by a user
(cafe, SaaS, retail, services, hospitality, etc.).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class Business(Base):
    """
    Business table - stores businesses owned by users.

    Examples:
    - Volume Cafe (food_and_beverage)
    - MySaaS Inc. (saas)
    - FashionStore (retail)
    """

    __tablename__ = "businesses"

    # ========================================================
    # Primary Key
    # ========================================================
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # ========================================================
    # Foreign Key (owner)
    # ========================================================
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ========================================================
    # Business Info
    # ========================================================
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    business_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    country_code: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )

    # ========================================================
    # Additional Metadata
    # ========================================================
    business_metadata: Mapped[dict] = mapped_column(
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

    # ========================================================
    # Timestamps
    # ========================================================
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
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="businesses",
    )

    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    initiatives: Mapped[list["Initiative"]] = relationship(
        "Initiative",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        "SocialAccount",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Business {self.name} ({self.business_type})>"