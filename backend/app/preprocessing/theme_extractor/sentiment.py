"""
Theme Extractor - Sentiment Helpers
===================================
Helpers for analyzing sentiment distributions.
"""
from typing import Dict


def dominant_sentiment(distribution: Dict[str, int]) -> str:
    """
    Determine the dominant sentiment label for a theme.
    
    Returns: 'positive', 'negative', 'neutral', or 'mixed'
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)
    total = pos + neg + neu + mix
    
    if total == 0:
        return "neutral"
    
    # If both positive and negative are significant, it's mixed
    if pos > 0 and neg > 0:
        ratio = min(pos, neg) / max(pos, neg)
        if ratio >= 0.5:
            return "mixed"
    
    # Find the dominant one
    counts = {"positive": pos, "negative": neg, "neutral": neu, "mixed": mix}
    return max(counts, key=counts.get)


def compute_sentiment_intensity(distribution: Dict[str, int]) -> float:
    """
    Compute 0.0-1.0 polarization score (how non-neutral the sentiment is).
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)
    total = pos + neg + neu + mix
    
    if total == 0:
        return 0.0
    
    polarized = pos + neg + mix
    return round(polarized / total, 3)


def sentiment_score(distribution: Dict[str, int]) -> float:
    """
    Compute scalar sentiment score in [-1.0, 1.0].
    +1 for fully positive, -1 for fully negative, 0 for neutral.
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)
    total = pos + neg + neu + mix
    
    if total == 0:
        return 0.0
    
    return round((pos - neg) / total, 3)


def combine_sentiment_distributions(
    a: Dict[str, int],
    b: Dict[str, int],
) -> Dict[str, int]:
    """
    Add two sentiment distributions together.
    """
    combined = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    for key in combined:
        combined[key] = a.get(key, 0) + b.get(key, 0)
    return combined