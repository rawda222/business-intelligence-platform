"""
SWOT Report Document Model
Stores complete SWOT analysis reports in MongoDB.
"""
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beanie import Document, Indexed
from pydantic import Field


class SWOTReportDocument(Document):
    """
    SWOT report document stored in MongoDB.
    
    Contains the full output from the SWOT Agent v7.0:
    - Strengths, Weaknesses, Opportunities, Threats
    - Watchouts
    - Strategic summary
    - Quality report
    """
    
    # ========================================================
    # Identification
    # ========================================================
    report_id: UUID = Field(default_factory=uuid4)
    business_id: UUID = Indexed()  # Index for fast lookup
    
    # ========================================================
    # Engine metadata
    # ========================================================
    engine_version: str = "7.0"
    business_type: str = "unknown"
    
    # ========================================================
    # SWOT Content
    # ========================================================
    swot_report: dict[str, Any] = Field(
        default_factory=dict,
        description="Main SWOT structure (strengths, weaknesses, opportunities, threats)",
    )
    
    watchouts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Early warning signals",
    )
    
    derived_opportunities: list[dict[str, Any]] = Field(
        default_factory=list,
    )
    
    directional_competitive_signals: list[dict[str, Any]] = Field(
        default_factory=list,
    )
    
    # ========================================================
    # Strategic Analysis
    # ========================================================
    strategic_summary: dict[str, Any] = Field(default_factory=dict)
    strategic_context: dict[str, Any] = Field(default_factory=dict)
    priority_insights: list[dict[str, Any]] = Field(default_factory=list)
    ambiguous_factors: list[dict[str, Any]] = Field(default_factory=list)
    
    # ========================================================
    # Matrix Outputs
    # ========================================================
    matrix_outputs: dict[str, Any] = Field(default_factory=dict)
    
    # ========================================================
    # Quality & Validation
    # ========================================================
    quality_report: dict[str, Any] = Field(default_factory=dict)
    validation_results: dict[str, Any] = Field(default_factory=dict)
    
    # ========================================================
    # Execution Metadata
    # ========================================================
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="LLM provider, model, cost, processing time, etc.",
    )
    
    # ========================================================
    # Timestamps
    # ========================================================
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "swot_reports"  # MongoDB collection name
        indexes = [
            "business_id",
            "created_at",
        ]
    
    def __repr__(self) -> str:
        return f"<SWOTReport business={self.business_id} created={self.created_at}>"