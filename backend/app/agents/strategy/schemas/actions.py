"""
Strategy Agent v1 - Priority Actions Schema
============================================
A ranked, ownable action derived from one or more TOWS strategies.
"""
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class PriorityAction(BaseModel):
    """A ranked, ownable action derived from one or more TOWS strategies."""
    model_config = ConfigDict(extra="ignore")
    
    action_id: str
    title: str
    description: str
    linked_strategy_ids: List[str] = Field(default_factory=list)
    horizon: str
    owner_area: str
    priority_rank: int
    confidence: str
    effort: str
    impact: str
    success_metric: str
    requires_manual_review: bool = False
    blocked_by: List[str] = Field(default_factory=list)