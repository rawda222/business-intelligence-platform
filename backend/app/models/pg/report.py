"""
Report Model
Stores metadata for SWOT and Strategy reports.
The actual content lives in MongoDB.
"""
from datetime import datetime
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class Report(Base):
    """
    Report metadata table.
    
    Each row tracks:
    - Which business it belongs to
    - What type (swot/strategy)
    - Status (pending/running/completed/failed)
    - Link to full content in MongoDB
    """
    __tablename__ = "reports"

    # ========================================================
    # Primary Key
    # ========================================================
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # ========================================================
    # Foreign Key (business)
    # ========================================================
    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ========================================================
    # Report Type
    # ========================================================
    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # swot, strategy
    )

    # ========================================================
    # MongoDB Link
    # ========================================================
    mongo_doc_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # ========================================================
    # Parent Report (Strategy depends on SWOT)
    # ========================================================
    parent_report_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reports.id"),
        nullable=True,
    )

    # ========================================================
    # Status & Execution
    # ========================================================
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        # pending, running, completed, failed
    )
    llm_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    llm_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # ========================================================
    # Timestamps
    # ========================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # Relationships
    # ========================================================
    business: Mapped["Business"] = relationship(
        "Business",
        back_populates="reports",
    )

    def __repr__(self) -> str:
        return f"<Report {self.report_type} status={self.status}>"