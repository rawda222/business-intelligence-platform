"""
Theme Extractor - Records
=========================
Build theme records and compute confidence scores.
"""
from typing import Any, Dict

from app.preprocessing.theme_extractor.config import (
    MIN_MENTIONS_FOR_BASE_CONFIDENCE,
)
from app.preprocessing.theme_extractor.taxonomy import PREDEFINED_THEMES


def build_theme_record(
    theme_key: str,
    entity_type: str,
    entry: Dict[str, Any],
    is_predefined: bool,
) -> Dict[str, Any]:
    """
    Build a single theme record (per theme_category + entity_type).
    
    Returns dict with:
    - theme_name
    - theme_category
    - entity_type
    - mentions
    - frequency_count
    - sentiment_distribution
    - representative_quotes
    - confidence_score
    - comparative_signal (filled later)
    """
    if is_predefined:
        display_name = PREDEFINED_THEMES[theme_key]["display_name"]
        theme_category = theme_key
    else:
        # Dynamic theme: 'emerging_<word>'
        word = theme_key[len("emerging_"):] if theme_key.startswith("emerging_") else theme_key
        display_name = f"Emerging Theme: {word.capitalize()}"
        theme_category = theme_key
    
    mentions = entry.get("mentions", [])
    sentiment_dist = entry.get("sentiment_distribution", {})
    quotes = entry.get("representative_quotes", [])
    
    frequency_count = len(mentions)
    
    confidence = compute_confidence_score(
        frequency_count=frequency_count,
        sentiment_distribution=sentiment_dist,
        is_predefined=is_predefined,
    )
    
    return {
        "theme_name": display_name,
        "theme_category": theme_category,
        "entity_type": entity_type,
        "mentions": mentions,
        "frequency_count": frequency_count,
        "sentiment_distribution": sentiment_dist,
        "representative_quotes": quotes,
        "confidence_score": confidence,
        "comparative_signal": "not_applicable",
        "_is_predefined": is_predefined,
        "_entity_names": list(entry.get("entity_names", set())),
    }


def compute_confidence_score(
    frequency_count: int,
    sentiment_distribution: Dict[str, int],
    is_predefined: bool,
) -> float:
    """
    Compute confidence score (0.0-1.0) for a theme record.
    
    Factors:
    - Base confidence (higher for predefined themes)
    - Mention count (more mentions = higher confidence)
    - Sentiment clarity (less neutral/unknown = higher confidence)
    """
    base = 0.5 if is_predefined else 0.35
    
    # Boost based on frequency
    if frequency_count >= MIN_MENTIONS_FOR_BASE_CONFIDENCE:
        frequency_boost = min(0.3, frequency_count * 0.05)
    else:
        frequency_boost = frequency_count * 0.025
    
    # Penalize if many unknowns
    total = sum(sentiment_distribution.values())
    if total > 0:
        polarized = sentiment_distribution.get("positive", 0) + \
                    sentiment_distribution.get("negative", 0)
        clarity_ratio = polarized / total
        clarity_boost = clarity_ratio * 0.15
    else:
        clarity_boost = 0.0
    
    confidence = base + frequency_boost + clarity_boost
    return round(min(1.0, confidence), 3)