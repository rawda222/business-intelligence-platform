"""
SWOT Agent v7 - Scoring Functions
==================================
Numeric scoring utilities for SWOT items.
"""
from app.agents.swot.config import (
    FREQUENCY_NORMALIZATION_CEILING,
    PRIORITY_WEIGHT_IMPORTANCE,
    PRIORITY_WEIGHT_IMPACT,
    PRIORITY_WEIGHT_CONFIDENCE,
    PRIORITY_WEIGHT_FREQUENCY,
)
from app.agents.swot.schemas.input import SentimentBalance


def normalize_frequency(freq: int) -> float:
    """
    Normalize a frequency count to a 0-10 scale.
    
    Examples:
        normalize_frequency(0) -> 0.0
        normalize_frequency(12) -> 4.8
        normalize_frequency(25) -> 10.0
        normalize_frequency(100) -> 10.0 (capped)
    """
    if freq <= 0:
        return 0.0
    return min(10.0, (freq / FREQUENCY_NORMALIZATION_CEILING) * 10.0)


def compute_sentiment_performance(sb: SentimentBalance) -> float:
    """
    FIX 5 - Sentiment-based performance score on a 0-10 scale.
    
    Weights:
        positive: 10.0
        mixed: 5.0
        neutral: 5.0
        negative: 0.0
    """
    t = sb.total
    if t == 0:
        return 5.0
    
    pos_r = sb.positive / t
    neg_r = sb.negative / t
    neu_r = sb.neutral / t
    mix_r = sb.mixed / t
    
    return (pos_r * 10.0) + (mix_r * 5.0) + (neu_r * 5.0) + (neg_r * 0.0)


def compute_strategic_priority(
    importance: float,
    impact: float,
    confidence: float,
    freq_norm: float,
) -> float:
    """
    Canonical strategic priority formula.
    
    Strategic Priority = 
        importance * 0.35 +
        impact * 0.25 +
        (confidence * 10) * 0.20 +
        freq_norm * 0.20
    """
    return (
        importance * PRIORITY_WEIGHT_IMPORTANCE
        + impact * PRIORITY_WEIGHT_IMPACT
        + (confidence * 10.0) * PRIORITY_WEIGHT_CONFIDENCE
        + freq_norm * PRIORITY_WEIGHT_FREQUENCY
    )


def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, v))