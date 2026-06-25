"""
Strategy Agent v1 - Resource Assessment Schema
===============================================
Effort x Impact grid entries for the resource assessment matrix.
"""
from pydantic import BaseModel, ConfigDict


class ResourceAssessmentEntry(BaseModel):
    """Effort x impact grid entry."""
    model_config = ConfigDict(extra="ignore")
    
    action_id: str
    title: str
    effort: str
    impact: str
    horizon: str
    quadrant_label: str   # quick_win | major_bet | fill_in | thankless