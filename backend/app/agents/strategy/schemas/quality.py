"""
Strategy Agent v1 - Quality Report Schema
==========================================
Quality gate output - mirrors the SWOT QualityReport discipline.
"""
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class StrategyQualityReport(BaseModel):
    """Quality gate output - mirrors the SWOT QualityReport discipline."""
    model_config = ConfigDict(extra="ignore")
    
    unanchored_strategies: List[str] = Field(default_factory=list)
    overconfident_claims: List[str] = Field(default_factory=list)
    empty_tows_cells: List[str] = Field(default_factory=list)
    manual_review_gates: List[str] = Field(default_factory=list)
    benchmark_language_violations: List[str] = Field(default_factory=list)
    overall_status: str = "PASS"
    warnings: List[str] = Field(default_factory=list)