"""
Strategy Agent v1 - Campaign Feed Builder
==========================================
Convert strategies into marketing-ready campaign feed.
"""
from typing import List

from app.agents.strategy.schemas.tows import TOWSMatrix
from app.agents.strategy.schemas.campaign import CampaignBriefFeedItem


# Only include strong strategies
ALLOWED_CONFIDENCE = {"confirmed", "probable", "exploratory"}


def build_campaign_feed(tows: TOWSMatrix) -> List[CampaignBriefFeedItem]:
    """
    Build marketing campaign feed from strategies.
    """
    strategies = (
        tows.SO +
        tows.ST +
        tows.WO +
        tows.WT
    )

    feed = []
    idx = 1

    for s in strategies:
        if s.confidence not in ALLOWED_CONFIDENCE:
            continue

        feed_item = CampaignBriefFeedItem(
            feed_id=f"CF_{idx}",
            source_strategy_id=s.strategy_id,
            source_swot_item_ids=[a.item_id for a in s.anchors],
            campaign_angle=_build_angle(s),
            messaging_pillar=_build_pillar(s),
            channel_suitability=_suggest_channels(s),
            confidence=s.confidence,
            requires_human_approval=(s.confidence != "confirmed"),
        )

        feed.append(feed_item)
        idx += 1

    return feed


def _build_angle(strategy) -> str:
    """Simple campaign angle generator."""
    return f"Leverage {strategy.title.lower()} to drive growth"


def _build_pillar(strategy) -> str:
    """Messaging pillar based on strategy type."""
    if strategy.strategy_type == "SO":
        return "growth"
    if strategy.strategy_type == "WO":
        return "improvement"
    if strategy.strategy_type == "ST":
        return "defense"
    if strategy.strategy_type == "WT":
        return "risk_mitigation"
    return "general"


def _suggest_channels(strategy) -> List[str]:
    """Suggest marketing channels."""
    if strategy.strategy_type == "SO":
        return ["social_media", "ads", "influencers"]
    if strategy.strategy_type == "WO":
        return ["email", "customer_feedback"]
    if strategy.strategy_type == "ST":
        return ["branding", "PR"]
    if strategy.strategy_type == "WT":
        return ["internal", "support"]
    return ["general"]