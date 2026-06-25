"""
Strategy Agent v1 - TOWS Matrix Schemas
========================================
Schemas for TOWS Matrix strategies and complete cross-matrix.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.agents.strategy.schemas.anchors import StrategyAnchor


class TOWSStrategy(BaseModel):
    """A single strategy generated from one TOWS cell."""
    model_config = ConfigDict(extra="ignore")
    
    strategy_id: str
    strategy_type: str   # SO | ST | WO | WT
    title: str
    description: str
    rationale: str
    anchors: List[StrategyAnchor] = Field(default_factory=list)
    confidence: str
    horizon: str
    estimated_effort: str
    estimated_impact: str
    priority_rank: int
    tags: List[str] = Field(default_factory=list)
    requires_manual_review: bool = False
    downstream_campaign_eligible: bool = False
    watchout_flag: Optional[str] = None


class TOWSMatrix(BaseModel):
    """Complete 4-cell TOWS cross-matrix."""
    model_config = ConfigDict(extra="ignore")
    
    SO: List[TOWSStrategy] = Field(default_factory=list)
    ST: List[TOWSStrategy] = Field(default_factory=list)
    WO: List[TOWSStrategy] = Field(default_factory=list)
    WT: List[TOWSStrategy] = Field(default_factory=list)