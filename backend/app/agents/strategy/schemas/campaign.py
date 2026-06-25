"""
Strategy Agent v1 - Campaign Brief Feed Schema
===============================================
Items passed to the Campaign Planner. Only confirmed/probable strategies.
"""
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class CampaignBriefFeedItem(BaseModel):
    """Item passed to Campaign Planner. Only confirmed/probable strategies."""
    model_config = ConfigDict(extra="ignore")
    
    feed_id: str
    source_strategy_id: str
    source_swot_item_ids: List[str] = Field(default_factory=list)
    campaign_angle: str
    messaging_pillar: str
    channel_suitability: List[str] = Field(default_factory=list)
    confidence: str
    requires_human_approval: bool = False