"""
Theme Extractor - Comparative Analysis
======================================
Compare target business against competitors for each theme category.
"""
from typing import Any, Dict, List

from app.preprocessing.theme_extractor.config import COMPARATIVE_GAP_THRESHOLD
from app.preprocessing.theme_extractor.sentiment import (
    sentiment_score,
    combine_sentiment_distributions,
)


def compute_comparative_signals(
    theme_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For each theme present in both target_business and competitor,
    produce a 'comparative' record and annotate individual records.
    """
    # Group records by theme_category
    by_theme: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    for record in theme_records:
        category = record["theme_category"]
        entity_type = record["entity_type"]
        
        if category not in by_theme:
            by_theme[category] = {}
        
        if entity_type not in by_theme[category]:
            by_theme[category][entity_type] = record
        else:
            # Merge if multiple records exist
            existing = by_theme[category][entity_type]
            existing["mentions"].extend(record["mentions"])
            existing["sentiment_distribution"] = combine_sentiment_distributions(
                existing["sentiment_distribution"],
                record["sentiment_distribution"],
            )
            existing["frequency_count"] = len(existing["mentions"])
    
    comparative_records = []
    
    # For each theme that has BOTH target_business and competitor
    for category, by_entity in by_theme.items():
        target = by_entity.get("target_business")
        competitor = by_entity.get("competitor")
        
        if not target or not competitor:
            continue
        
        # Compute sentiment scores
        target_score = sentiment_score(target["sentiment_distribution"])
        competitor_score = sentiment_score(competitor["sentiment_distribution"])
        
        # Determine comparative signal
        gap = target_score - competitor_score
        
        if gap > COMPARATIVE_GAP_THRESHOLD:
            signal = "overperforms"
        elif gap < -COMPARATIVE_GAP_THRESHOLD:
            signal = "underperforms"
        else:
            signal = "parity"
        
        # Annotate individual records
        target["comparative_signal"] = signal
        if signal == "overperforms":
            competitor["comparative_signal"] = "underperforms"
        elif signal == "underperforms":
            competitor["comparative_signal"] = "overperforms"
        else:
            competitor["comparative_signal"] = "parity"
        
        # Build comparative record
        combined_mentions = list(target["mentions"]) + list(competitor["mentions"])
        combined_sentiment = combine_sentiment_distributions(
            target["sentiment_distribution"],
            competitor["sentiment_distribution"],
        )
        combined_quotes = (
            list(target.get("representative_quotes", []))
            + list(competitor.get("representative_quotes", []))
        )[:3]
        
        avg_confidence = round(
            (target.get("confidence_score", 0.5) + competitor.get("confidence_score", 0.5)) / 2,
            3,
        )
        
        comparative_records.append({
            "theme_name": target["theme_name"],
            "theme_category": category,
            "entity_type": "comparative",
            "mentions": combined_mentions,
            "frequency_count": len(combined_mentions),
            "sentiment_distribution": combined_sentiment,
            "representative_quotes": combined_quotes,
            "confidence_score": avg_confidence,
            "comparative_signal": signal,
            "_target_score": target_score,
            "_competitor_score": competitor_score,
            "_gap": round(gap, 3),
        })
    
    return comparative_records


def build_comparison_summary(
    comparative_records: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Build summary of theme categories where target overperforms/underperforms.
    """
    overperforms: List[str] = []
    underperforms: List[str] = []
    parity: List[str] = []
    
    for record in comparative_records:
        signal = record.get("comparative_signal")
        category = record["theme_category"]
        
        if signal == "overperforms":
            overperforms.append(category)
        elif signal == "underperforms":
            underperforms.append(category)
        elif signal == "parity":
            parity.append(category)
    
    return {
        "overperforms": sorted(set(overperforms)),
        "underperforms": sorted(set(underperforms)),
        "parity": sorted(set(parity)),
    }