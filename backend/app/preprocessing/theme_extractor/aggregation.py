"""
Theme Extractor - Aggregation
=============================
Aggregate theme data across reviews.

For each (theme_category, entity_type) pair, collect:
- mentions (review_ids)
- sentiment_distribution
- representative quotes
- entity_names (for comparative signal)
"""
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.preprocessing.theme_extractor.config import MAX_REPRESENTATIVE_QUOTES
from app.preprocessing.theme_extractor.reviews import get_review_text, is_usable
from app.preprocessing.theme_extractor.detection import (
    detect_theme_categories_for_review,
)


def aggregate_theme_data(
    reviews: List[Dict[str, Any]],
) -> Tuple[
    Dict[Tuple[str, str], Dict[str, Any]],
    Dict[str, List[str]],
]:
    """
    Aggregate theme data from reviews.
    
    Returns:
        (aggregates, matched_theme_map)
        
        aggregates: Dict keyed by (theme_category, entity_type) ->
            {
                "mentions": list[review_id],
                "sentiment_distribution": dict,
                "representative_quotes": list[str],
                "entity_names": set,
            }
        
        matched_theme_map: Dict[review_id, list[theme_category]]
    """
    aggregates: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "mentions": [],
            "sentiment_distribution": {
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "mixed": 0,
            },
            "representative_quotes": [],
            "entity_names": set(),
        }
    )
    
    matched_theme_map: Dict[str, List[str]] = defaultdict(list)
    
    for review in reviews:
        if not is_usable(review):
            continue
        
        review_id = review.get("review_id")
        entity_type = review.get("entity_type") or "unknown"
        entity_name = review.get("entity_name") or "unknown"
        sentiment = review.get("sentiment_hint") or "unknown"
        text = get_review_text(review)
        
        # Detect themes for this review
        themes = detect_theme_categories_for_review(review)
        
        # Track which themes matched this review
        matched_theme_map[review_id].extend(themes)
        
        # Add to aggregates
        for theme_key in themes:
            key = (theme_key, entity_type)
            agg = aggregates[key]
            
            # Add mention
            if review_id and review_id not in agg["mentions"]:
                agg["mentions"].append(review_id)
            
            # Update sentiment distribution
            if sentiment in agg["sentiment_distribution"]:
                agg["sentiment_distribution"][sentiment] += 1
            elif sentiment != "unknown":
                # Unknown sentiments don't count
                pass
            
            # Add representative quote (cap at MAX)
            if text and len(agg["representative_quotes"]) < MAX_REPRESENTATIVE_QUOTES:
                if text not in agg["representative_quotes"]:
                    agg["representative_quotes"].append(text)
            
            # Track entity name
            agg["entity_names"].add(entity_name)
    
    return aggregates, matched_theme_map


def aggregate_dynamic_theme_data(
    reviews: List[Dict[str, Any]],
    dynamic_themes: Dict[str, List[str]],
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Aggregate dynamically discovered themes (split by entity_type).
    """
    review_lookup = {
        r.get("review_id"): r
        for r in reviews
        if r.get("review_id")
    }
    
    aggregates: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "mentions": [],
            "sentiment_distribution": {
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "mixed": 0,
            },
            "representative_quotes": [],
            "entity_names": set(),
        }
    )
    
    for theme_key, review_ids in dynamic_themes.items():
        for review_id in review_ids:
            review = review_lookup.get(review_id)
            if not review:
                continue
            
            entity_type = review.get("entity_type") or "unknown"
            entity_name = review.get("entity_name") or "unknown"
            sentiment = review.get("sentiment_hint") or "unknown"
            text = get_review_text(review)
            
            key = (theme_key, entity_type)
            agg = aggregates[key]
            
            if review_id not in agg["mentions"]:
                agg["mentions"].append(review_id)
            
            if sentiment in agg["sentiment_distribution"]:
                agg["sentiment_distribution"][sentiment] += 1
            
            if text and len(agg["representative_quotes"]) < MAX_REPRESENTATIVE_QUOTES:
                if text not in agg["representative_quotes"]:
                    agg["representative_quotes"].append(text)
            
            agg["entity_names"].add(entity_name)
    
    return aggregates