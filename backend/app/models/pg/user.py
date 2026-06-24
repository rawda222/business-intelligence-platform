"""
User Model
Represents application users (business owners).
"""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.db.postgres import Base


class User(Base):
    """
    User table - stores user accounts.
    
    Each user can own multiple businesses.
    """
    __tablename__ = "users"

    # ========================================================
    # Primary Key
    # ========================================================
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # ========================================================
    # Authentication
    # ========================================================
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ========================================================
    # Profile
    # ========================================================
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ========================================================
    # Status & Role
    # ========================================================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default="user",  # user, admin
    )

    # ========================================================
    # Timestamps
    # ========================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ========================================================
    # Relationships
    # ========================================================
    # One user can own many businesses
    businesses: Mapped[list["Business"]] = relationship(
        "Business",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"