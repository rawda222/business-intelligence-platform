"""
SWOT Agent v7 - Stage 1: Theme Validation
==========================================
Filter themes that do not meet minimum evidence requirements.
"""
import logging
from typing import List, Tuple

from app.agents.swot.schemas.input import ReviewTheme
from app.agents.swot.config import MIN_THEME_FREQUENCY, MIN_SENTIMENT_TOTAL


logger = logging.getLogger("swot_agent_v7")


def validate_review_themes(
    themes: List[ReviewTheme],
) -> Tuple[List[ReviewTheme], int]:
    """
    Filter themes that do not meet minimum evidence requirements.
    
    Filters out themes with:
    - frequency < MIN_THEME_FREQUENCY
    - sentiment_total < MIN_SENTIMENT_TOTAL
    
    Returns:
        (kept_themes, filtered_count)
    """
    kept = []
    filtered_count = 0
    
    for theme in themes:
        # Check frequency
        if theme.frequency < MIN_THEME_FREQUENCY:
            filtered_count += 1
            logger.debug(
                f"[Stage 1] Filtered theme '{theme.theme_category}' "
                f"(freq={theme.frequency} < {MIN_THEME_FREQUENCY})"
            )
            continue
        
        # Check sentiment total
        if theme.sentiment_balance.total < MIN_SENTIMENT_TOTAL:
            filtered_count += 1
            logger.debug(
                f"[Stage 1] Filtered theme '{theme.theme_category}' "
                f"(sentiment_total={theme.sentiment_balance.total} < {MIN_SENTIMENT_TOTAL})"
            )
            continue
        
        kept.append(theme)
    
    logger.info(
        f"[Stage 1] Kept {len(kept)}/{len(themes)} themes, "
        f"filtered {filtered_count}"
    )
    
    return kept, filtered_count