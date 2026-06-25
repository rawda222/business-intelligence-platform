"""
SWOT Agent v7 - Stage 2: Semantic Theme Merging
================================================
Merge semantically similar themes BEFORE the LLM stage.
"""
import logging
from typing import Dict, List

from app.agents.swot.schemas.input import ReviewTheme, SentimentBalance
from app.agents.swot.processors.theme_aliases import THEME_ALIAS_MAP


logger = logging.getLogger("swot_agent_v7")


def normalize_and_merge_similar_themes(
    themes: List[ReviewTheme],
) -> List[ReviewTheme]:
    """
    Merge semantically similar themes BEFORE the LLM stage.
    
    Example: 'staff_behavior' + 'service_speed' -> 'service'
    
    Combines:
    - frequency (sum)
    - sentiment_balance (sum each)
    - mentions (concat)
    - evidence_refs (concat)
    """
    # Group themes by (canonical_category, entity_type)
    groups: Dict[tuple, List[ReviewTheme]] = {}
    
    for theme in themes:
        canonical = THEME_ALIAS_MAP.get(theme.theme_category, theme.theme_category)
        key = (canonical, theme.entity_type)
        
        if key not in groups:
            groups[key] = []
        groups[key].append(theme)
    
    # Merge each group
    merged = []
    for (canonical, entity_type), group_themes in groups.items():
        if len(group_themes) == 1:
            # No merging needed, but update category name
            t = group_themes[0]
            t.theme_category = canonical
            merged.append(t)
        else:
            merged_theme = _merge_theme_group(canonical, entity_type, group_themes)
            merged.append(merged_theme)
            logger.info(
                f"[Stage 2] Merged {len(group_themes)} themes into "
                f"'{canonical}' ({entity_type})"
            )
    
    logger.info(
        f"[Stage 2] Reduced {len(themes)} themes to {len(merged)} after merging"
    )
    
    return merged


def merge_themes_by_category(
    themes: List[ReviewTheme],
) -> Dict[str, Dict[str, ReviewTheme]]:
    """
    Group themes by theme_category, indexed by entity_type.
    
    Returns:
        {category: {entity_type: ReviewTheme}}
    """
    grouped: Dict[str, Dict[str, ReviewTheme]] = {}
    
    for theme in themes:
        if theme.theme_category not in grouped:
            grouped[theme.theme_category] = {}
        grouped[theme.theme_category][theme.entity_type] = theme
    
    return grouped


def _merge_theme_group(
    canonical: str,
    entity_type: str,
    themes: List[ReviewTheme],
) -> ReviewTheme:
    """Merge a list of themes into a single theme."""
    # Sum frequencies
    total_freq = sum(t.frequency for t in themes)
    
    # Sum sentiment balances
    merged_sentiment = SentimentBalance(
        positive=sum(t.sentiment_balance.positive for t in themes),
        negative=sum(t.sentiment_balance.negative for t in themes),
        neutral=sum(t.sentiment_balance.neutral for t in themes),
        mixed=sum(t.sentiment_balance.mixed for t in themes),
    )
    
    # Concat mentions and evidence
    all_mentions = []
    all_evidence = []
    for t in themes:
        all_mentions.extend(t.mentions)
        all_evidence.extend(t.evidence_refs)
    
    # Average scores (if available)
    target_scores = [t.target_score for t in themes if t.target_score is not None]
    competitor_scores = [t.competitor_score for t in themes if t.competitor_score is not None]
    
    avg_target = sum(target_scores) / len(target_scores) if target_scores else None
    avg_competitor = sum(competitor_scores) / len(competitor_scores) if competitor_scores else None
    
    return ReviewTheme(
        theme_category=canonical,
        entity_type=entity_type,
        frequency=total_freq,
        sentiment_balance=merged_sentiment,
        target_score=avg_target,
        competitor_score=avg_competitor,
        performance_gap=(
            avg_target - avg_competitor
            if (avg_target is not None and avg_competitor is not None)
            else None
        ),
        mentions=all_mentions,
        evidence_refs=all_evidence,
    )