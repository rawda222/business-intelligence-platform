"""
SWOT Agent v7 - Confidence Calculations
========================================
Compute confidence scores for themes and comparisons.
"""
from typing import Dict, Optional, Tuple

from app.agents.swot.schemas.input import ReviewTheme
from app.agents.swot.enums import ClaimStrength


def compute_theme_confidence(theme: ReviewTheme) -> float:
    """
    Compute a confidence score in [0, 1] based on theme frequency
    and sentiment_total.
    
    More mentions + clearer sentiment = higher confidence.
    """
    freq = theme.frequency
    sent_total = theme.sentiment_balance.total
    
    if freq == 0 or sent_total == 0:
        return 0.0
    
    # Base confidence from frequency
    freq_score = min(1.0, freq / 10.0)
    
    # Sentiment clarity (less neutral = higher confidence)
    pos = theme.sentiment_balance.positive
    neg = theme.sentiment_balance.negative
    clarity = (pos + neg) / sent_total if sent_total > 0 else 0.0
    
    # Combined
    confidence = (freq_score * 0.6) + (clarity * 0.4)
    return round(min(1.0, confidence), 3)


def apply_comparison_confidence(
    target: Optional[ReviewTheme],
    competitor: Optional[ReviewTheme],
    competitor_review_counts: Dict[str, int],
) -> Tuple[Optional[float], str]:
    """
    Compute a comparison confidence and the recommended claim_strength.
    
    Returns:
        (confidence, claim_strength)
    
    Logic:
    - If both target and competitor have data -> can compare
    - More competitor reviews -> higher confidence
    - Few reviews -> directional only
    """
    if not target or not competitor:
        return None, ClaimStrength.EARLY_WARNING.value
    
    target_freq = target.frequency
    comp_freq = competitor.frequency
    
    if target_freq < 2 or comp_freq < 2:
        return 0.3, ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
    
    # Average competitor reviews available
    total_comp_reviews = sum(competitor_review_counts.values())
    avg_reviews = (
        total_comp_reviews / len(competitor_review_counts)
        if competitor_review_counts else 0
    )
    
    if avg_reviews >= 10:
        return 0.8, ClaimStrength.VALIDATED.value
    elif avg_reviews >= 5:
        return 0.6, ClaimStrength.INTERNALLY_SUPPORTED.value
    else:
        return 0.4, ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value