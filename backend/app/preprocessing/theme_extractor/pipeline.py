"""
Theme Extractor - Main Pipeline
===============================
Top-level orchestration for theme extraction.

Pipeline:
1. Collect all reviews (target + competitors)
2. Aggregate themes from reviews
3. Discover dynamic (emerging) themes
4. Aggregate dynamic themes
5. Build theme records
6. Compute comparative signals
7. Extract positive/negative/opportunity/threat signals
8. Rank themes by strategic importance
9. Build final output
"""
from typing import Any, Dict, List

from app.preprocessing.theme_extractor.reviews import collect_all_reviews
from app.preprocessing.theme_extractor.detection import discover_dynamic_themes
from app.preprocessing.theme_extractor.aggregation import (
    aggregate_theme_data,
    aggregate_dynamic_theme_data,
)
from app.preprocessing.theme_extractor.records import build_theme_record
from app.preprocessing.theme_extractor.comparative import (
    compute_comparative_signals,
    build_comparison_summary,
)
from app.preprocessing.theme_extractor.signals import extract_signals
from app.preprocessing.theme_extractor.ranking import (
    rank_themes,
    strip_internal_fields,
)


def extract_themes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main extraction pipeline.
    
    Args:
        data: Normalized data dict (from normalize.normalize_raw_data)
    
    Returns:
        Theme analysis dict with:
        - themes: list of theme records (ranked)
        - positive_signals
        - negative_signals
        - opportunity_signals
        - threat_signals
        - comparison_summary
    """
    # 1. Collect all reviews
    reviews = collect_all_reviews(data)
    
    if not reviews:
        return _empty_output()
    
    # 2. Aggregate predefined themes
    predefined_aggregates, matched_theme_map = aggregate_theme_data(reviews)
    
    # 3. Discover dynamic (emerging) themes
    dynamic_themes = discover_dynamic_themes(reviews, matched_theme_map)
    
    # 4. Aggregate dynamic themes
    dynamic_aggregates = aggregate_dynamic_theme_data(reviews, dynamic_themes)
    
    # 5. Build theme records (predefined + dynamic)
    theme_records: List[Dict[str, Any]] = []
    
    for (theme_key, entity_type), entry in predefined_aggregates.items():
        record = build_theme_record(
            theme_key=theme_key,
            entity_type=entity_type,
            entry=entry,
            is_predefined=True,
        )
        theme_records.append(record)
    
    for (theme_key, entity_type), entry in dynamic_aggregates.items():
        record = build_theme_record(
            theme_key=theme_key,
            entity_type=entity_type,
            entry=entry,
            is_predefined=False,
        )
        theme_records.append(record)
    
    # 6. Compute comparative signals (annotates records + adds comparative records)
    comparative_records = compute_comparative_signals(theme_records)
    theme_records.extend(comparative_records)
    
    # 7. Extract signals
    positive, negative, opportunity, threat = extract_signals(theme_records)
    
    # 8. Build comparison summary
    comparison_summary = build_comparison_summary(comparative_records)
    
    # 9. Rank themes by strategic importance
    ranked = rank_themes(theme_records)
    
    # 10. Strip internal fields
    cleaned_themes = [strip_internal_fields(r) for r in ranked]
    
    return {
        "themes": cleaned_themes,
        "positive_signals": positive,
        "negative_signals": negative,
        "opportunity_signals": opportunity,
        "threat_signals": threat,
        "comparison_summary": comparison_summary,
    }


def extract_themes_from_normalized(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public entry point (matches the legacy theme_extractor signature).
    
    Args:
        normalized_data: Output from normalize.normalize_raw_data
    
    Returns:
        Theme analysis dict
    """
    return extract_themes(normalized_data)


def _empty_output() -> Dict[str, Any]:
    """Return empty output structure when no reviews available."""
    return {
        "themes": [],
        "positive_signals": [],
        "negative_signals": [],
        "opportunity_signals": [],
        "threat_signals": [],
        "comparison_summary": {
            "overperforms": [],
            "underperforms": [],
            "parity": [],
        },
    }