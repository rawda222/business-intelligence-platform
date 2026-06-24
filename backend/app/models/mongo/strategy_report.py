"""
Strategy Report Document Model
Stores Strategy Agent outputs in MongoDB.
"""
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beanie import Document, Indexed
from pydantic import Field


class StrategyReportDocument(Document):
    """
    Strategy report document stored in MongoDB.
    
    Contains the full output from the Strategy Agent:
    - TOWS synthesis
    - Strategic initiatives
    - Roadmap
    - Execution notes
    """
    
    # ========================================================
    # Identification
    # ========================================================
    report_id: UUID = Field(default_factory=uuid4)
    business_id: UUID = Indexed()
    source_swot_id: UUID  # Links to SWOT report
    
    # ========================================================
    # Engine metadata
    # ========================================================
    engine_version: str = "1.0"
    
    # ========================================================
    # Strategy Content
    # ========================================================
    meta: dict[str, Any] = Field(default_factory=dict)
    
    tows_synthesis: dict[str, Any] = Field(
        default_factory=dict,
        description="SO/ST/WO/WT logic",
    )
    
    initiatives: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Strategic initiatives generated",
    )
    
    strategic_recommendations: dict[str, Any] = Field(default_factory=dict)
    execution_notes: dict[str, Any] = Field(default_factory=dict)
    
    # ========================================================
    # Timestamps
    # ========================================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "strategy_reports"
        indexes = [
            "business_id",
            "source_swot_id",
            "created_at",
        ]
    
    def __repr__(self) -> str:
        return f"<StrategyReport business={self.business_id} created={self.created_at}>"