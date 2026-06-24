"""
Theme Extractor - Signal Extraction
===================================
Derive positive/negative/opportunity/threat signals from theme records.
"""
from typing import Any, Dict, List, Tuple

from app.preprocessing.theme_extractor.config import (
    POSITIVE_SIGNAL_RATIO,
    NEGATIVE_SIGNAL_RATIO,
)


def extract_signals(
    theme_records: List[Dict[str, Any]],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """
    Extract 4 signal categories:
    - positive_signals: themes with strong positive sentiment (target only)
    - negative_signals: themes with strong negative sentiment (target only)
    - opportunity_signals: themes where target overperforms vs competitors
    - threat_signals: themes where target underperforms vs competitors
    
    Returns:
        (positive, negative, opportunity, threat)
    """
    positive = []
    negative = []
    opportunity = []
    threat = []
    
    for record in theme_records:
        entity_type = record["entity_type"]
        sentiment_dist = record["sentiment_distribution"]
        
        total = sum(sentiment_dist.values())
        if total == 0:
            continue
        
        pos_ratio = sentiment_dist.get("positive", 0) / total
        neg_ratio = sentiment_dist.get("negative", 0) / total
        
        # Positive/Negative signals only for target_business
        if entity_type == "target_business":
            if pos_ratio >= POSITIVE_SIGNAL_RATIO:
                positive.append(_signal_summary(record, "high_positive_sentiment"))
            elif neg_ratio >= NEGATIVE_SIGNAL_RATIO:
                negative.append(_signal_summary(record, "high_negative_sentiment"))
        
        # Opportunity/Threat signals from comparative records
        if entity_type == "comparative":
            signal = record.get("comparative_signal")
            if signal == "overperforms":
                opportunity.append(_signal_summary(record, "overperforms_competitors"))
            elif signal == "underperforms":
                threat.append(_signal_summary(record, "underperforms_competitors"))
    
    return positive, negative, opportunity, threat


def _signal_summary(record: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Build a compact signal summary from a theme record."""
    return {
        "theme_name": record["theme_name"],
        "theme_category": record["theme_category"],
        "entity_type": record["entity_type"],
        "reason": reason,
        "frequency_count": record["frequency_count"],
        "sentiment_distribution": record["sentiment_distribution"],
        "confidence_score": record["confidence_score"],
        "mentions": record["mentions"],
    }