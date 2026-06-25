"""
SWOT Agent v7 - Stage 5: Shadow Routing (FIX 2)
================================================
Route shadow weaknesses to watchouts by default.

A "shadow weakness" is a minor negative signal in an otherwise positive
theme. They should NOT promote to confirmed weakness without strong
evidence - instead routed to "watchouts" for downstream review.
"""
import logging
from typing import List, Tuple

from app.agents.swot.schemas.output import SWOTItem, WatchoutItem, EvidenceSummary
from app.agents.swot.schemas.input import ReviewTheme
from app.agents.swot.config import (
    SHADOW_PROMOTION_RULES,
    SHADOW_MIN_NEGATIVE_MIX_RATIO,
)
from app.agents.swot.enums import ClaimStrength
from app.agents.swot.utils.slugify import slugify


logger = logging.getLogger("swot_agent_v7")


def route_shadows_to_watchouts(
    weaknesses: List[SWOTItem],
    themes_by_category: dict,
) -> Tuple[List[SWOTItem], List[WatchoutItem]]:
    """
    FIX 2: Separate confirmed weaknesses from shadow weaknesses.
    
    Shadows are routed to watchouts unless:
    - negative_ratio >= 0.35
    - negative_mentions >= 3
    
    Even when promotion threshold is met, shadows require manual_review.
    
    Returns:
        (confirmed_weaknesses, watchouts)
    """
    confirmed_weaknesses = []
    watchouts = []
    
    min_neg_ratio = SHADOW_PROMOTION_RULES["min_negative_ratio"]
    min_neg_mentions = SHADOW_PROMOTION_RULES["min_negative_mentions"]
    
    for item in weaknesses:
        theme_data = _get_theme_data(item.source_theme, themes_by_category)
        
        if not theme_data:
            # No theme data - keep as confirmed (LLM judgment)
            confirmed_weaknesses.append(item)
            continue
        
        sb = theme_data.sentiment_balance
        total = sb.total
        
        if total == 0:
            confirmed_weaknesses.append(item)
            continue
        
        neg_ratio = sb.negative / total
        
        # Check if shadow
        is_shadow = neg_ratio < min_neg_ratio or sb.negative < min_neg_mentions
        
        if is_shadow:
            # Route to watchout
            watchout = WatchoutItem(
                watchout_id=f"WO_{slugify(item.title)}",
                title=f"Watchout: {item.title}",
                parent_item_id=item.item_id,
                parent_theme=item.source_theme,
                reasoning=item.reasoning,
                severity="low" if neg_ratio < SHADOW_MIN_NEGATIVE_MIX_RATIO else "medium",
                scope="internal",
                manual_review_only=True,
                evidence_refs=item.evidence_refs,
                evidence_summary=item.evidence_summary,
                recommended_action="Monitor closely - insufficient evidence for confirmed weakness",
                claim_strength=ClaimStrength.EARLY_WARNING.value,
                is_shadow=True,
                should_feed_strategy_agent=False,
                should_feed_campaign_planner=False,
                low_benchmark_quality=item.low_benchmark_quality,
            )
            watchouts.append(watchout)
            logger.debug(
                f"[Stage 5] Routed '{item.title}' to watchout "
                f"(neg_ratio={neg_ratio:.2%})"
            )
        else:
            # Promote to confirmed weakness
            item.is_shadow = False
            item.manual_review_only = SHADOW_PROMOTION_RULES["requires_manual_review"]
            confirmed_weaknesses.append(item)
            logger.debug(
                f"[Stage 5] Promoted '{item.title}' to confirmed weakness "
                f"(neg_ratio={neg_ratio:.2%})"
            )
    
    logger.info(
        f"[Stage 5] Shadow routing: {len(confirmed_weaknesses)} confirmed, "
        f"{len(watchouts)} watchouts"
    )
    
    return confirmed_weaknesses, watchouts


def _get_theme_data(source_theme: str, themes_by_category: dict):
    """Lookup theme data by source_theme name."""
    if source_theme in themes_by_category:
        entity_dict = themes_by_category[source_theme]
        # Prefer target_business entity_type
        for entity_type in ("target_business", "comparative"):
            if entity_type in entity_dict:
                return entity_dict[entity_type]
        # Fallback: any entity type
        for theme in entity_dict.values():
            return theme
    return None