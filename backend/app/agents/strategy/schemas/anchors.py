"""
Strategy Agent v1 - Strategy Anchors
=====================================
Schema for SWOT items that anchor a strategy.
"""
from pydantic import BaseModel, ConfigDict


class StrategyAnchor(BaseModel):
    """A SWOT item that anchors a strategy."""
    model_config = ConfigDict(extra="ignore")
    
    item_id: str
    title: str
    quadrant: str
    confidence: str
    strategic_priority: float = 0.0