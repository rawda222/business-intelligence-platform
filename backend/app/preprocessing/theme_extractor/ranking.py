"""
Theme Extractor - Ranking
=========================
Rank themes by strategic importance.
"""
from typing import Any, Dict, List

from app.preprocessing.theme_extractor.taxonomy import PREDEFINED_THEME_ORDER


def compute_strategic_score(record: Dict[str, Any]) -> float:
    """
    Compute a strategic importance score for ranking themes.
    
    Factors:
    - Frequency (higher = more strategic)
    - Confidence (higher = more reliable)
    - Comparative signal (overperforms/underperforms boost score)
    - Sentiment polarity (extreme sentiment = more strategic)
    """
    frequency = record.get("frequency_count", 0)
    confidence = record.get("confidence_score", 0.5)
    signal = record.get("comparative_signal", "not_applicable")
    
    # Base: frequency * confidence
    base = frequency * confidence
    
    # Boost for comparative signals
    signal_boost = {
        "overperforms": 1.5,
        "underperforms": 1.5,
        "parity": 1.0,
        "not_applicable": 1.0,
    }.get(signal, 1.0)
    
    # Boost for sentiment polarity
    sentiment_dist = record.get("sentiment_distribution", {})
    total = sum(sentiment_dist.values())
    if total > 0:
        pos = sentiment_dist.get("positive", 0)
        neg = sentiment_dist.get("negative", 0)
        polarity = abs(pos - neg) / total
        sentiment_boost = 1.0 + polarity * 0.3
    else:
        sentiment_boost = 1.0
    
    score = base * signal_boost * sentiment_boost
    return round(score, 3)


def rank_themes(theme_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort themes by strategic score (descending).
    
    Tie-breakers:
    1. Predefined theme order
    2. Entity type (target_business > competitor > comparative)
    3. Theme name (alphabetical)
    """
    def category_sort_key(category: str) -> int:
        if category in PREDEFINED_THEME_ORDER:
            return PREDEFINED_THEME_ORDER.index(category)
        return len(PREDEFINED_THEME_ORDER) + 1
    
    def entity_sort_key(entity_type: str) -> int:
        order = {
            "target_business": 0,
            "comparative": 1,
            "competitor": 2,
        }
        return order.get(entity_type, 99)
    
    # Compute strategic scores
    for record in theme_records:
        record["_strategic_score"] = compute_strategic_score(record)
    
    # Sort
    return sorted(
        theme_records,
        key=lambda r: (
            -r["_strategic_score"],
            category_sort_key(r["theme_category"]),
            entity_sort_key(r["entity_type"]),
            r["theme_name"],
        ),
    )


def strip_internal_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Remove internal-use-only keys (prefixed with '_')."""
    return {k: v for k, v in record.items() if not k.startswith("_")}