"""
SWOT Agent v7 - Stage 1: Theme Validation
==========================================
Filter themes that do not meet minimum evidence requirements.

Thresholds adapt to the available theme volume so that small
datasets still yield a (low-confidence) SWOT instead of an empty one.
Richer datasets keep the original strict thresholds.
"""
import logging
from typing import List, Tuple

from app.agents.swot.schemas.input import ReviewTheme
from app.agents.swot.config import (
    MIN_THEME_FREQUENCY,
    MIN_SENTIMENT_TOTAL,
)


logger = logging.getLogger("swot_agent_v7")


def _resolve_thresholds(theme_count: int) -> Tuple[int, int]:
    """
    Scale evidence thresholds to the available theme volume.

    Small datasets relax to 1 so the pipeline stays analyzable;
    the low confidence is reflected downstream via claim_strength.
    """
    if theme_count < 8:
        return 1, 1
    return MIN_THEME_FREQUENCY, MIN_SENTIMENT_TOTAL


def validate_review_themes(
    themes: List[ReviewTheme],
) -> Tuple[List[ReviewTheme], int]:
    """
    Filter themes that do not meet the (adaptive) minimum
    evidence requirements.

    Returns:
        (kept_themes, filtered_count)
    """
    min_frequency, min_sentiment = _resolve_thresholds(len(themes))

    kept: List[ReviewTheme] = []
    filtered_count = 0

    for theme in themes:
        if theme.frequency < min_frequency:
            filtered_count += 1
            logger.debug(
                "[Stage 1] Filtered '%s' (freq=%s < %s)",
                theme.theme_category, theme.frequency, min_frequency,
            )
            continue

        if theme.sentiment_balance.total < min_sentiment:
            filtered_count += 1
            logger.debug(
                "[Stage 1] Filtered '%s' (sentiment_total=%s < %s)",
                theme.theme_category,
                theme.sentiment_balance.total,
                min_sentiment,
            )
            continue

        kept.append(theme)

    logger.info(
        "[Stage 1] Kept %d/%d themes "
        "(min_freq=%d, min_sentiment=%d), filtered %d",
        len(kept), len(themes),
        min_frequency, min_sentiment, filtered_count,
    )

    return kept, filtered_count