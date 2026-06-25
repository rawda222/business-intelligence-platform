"""
Strategy Agent v1 - Top-Level Output Schema
============================================
The final StrategyOutput consumed by Brief Generator.
"""
from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict, Field

from app.agents.strategy.config import ENGINE_VERSION
from app.agents.strategy.enums import StrategicPosture
from app.agents.strategy.schemas.tows import TOWSMatrix
from app.agents.strategy.schemas.actions import PriorityAction
from app.agents.strategy.schemas.resources import ResourceAssessmentEntry
from app.agents.strategy.schemas.campaign import CampaignBriefFeedItem
from app.agents.strategy.schemas.quality import StrategyQualityReport


class StrategyOutput(BaseModel):
    """Top-level output of the Strategy Agent."""
    model_config = ConfigDict(extra="ignore")
    
    business_type: str = "unknown"
    engine_version: str = ENGINE_VERSION
    strategic_posture: str = StrategicPosture.BALANCED
    posture_rationale: str = ""
    tows_matrix: TOWSMatrix = Field(default_factory=TOWSMatrix)
    priority_action_plan: List[PriorityAction] = Field(default_factory=list)
    resource_assessment: List[ResourceAssessmentEntry] = Field(default_factory=list)
    campaign_brief_feed: List[CampaignBriefFeedItem] = Field(default_factory=list)
    strategy_quality_report: StrategyQualityReport = Field(default_factory=StrategyQualityReport)
    meta: Dict[str, Any] = Field(default_factory=dict)