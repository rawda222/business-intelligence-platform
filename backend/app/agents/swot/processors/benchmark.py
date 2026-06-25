"""
SWOT Agent v7 - Benchmark Quality Assessment
=============================================
Conservative benchmark quality classification (FIX 4).
"""
from typing import Any, Dict, Tuple

from app.agents.swot.config import (
    BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR,
    BENCHMARK_MEDIUM_MIN_COMPETITORS_AT_THRESHOLD,
    RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR,
)


def assess_benchmark_quality(
    competitor_review_counts: Dict[str, int],
) -> Tuple[str, Dict[str, Any]]:
    """
    Conservative benchmark quality assessment (FIX 4).
    
    Quality tiers:
    - high: >= 2 competitors with >= 10 reviews each
    - medium: >= 1 competitor with >= 10 reviews
    - low: at least 1 competitor with some reviews
    - unavailable: no competitor data
    
    Returns:
        (quality_label, summary_dict)
    """
    if not competitor_review_counts:
        return "unavailable", {
            "total_competitors": 0,
            "competitors_at_threshold": 0,
            "min_reviews_seen": 0,
            "max_reviews_seen": 0,
            "recommended_min_reviews": RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR,
        }
    
    total_competitors = len(competitor_review_counts)
    review_counts = list(competitor_review_counts.values())
    
    # Count competitors at threshold
    competitors_at_threshold = sum(
        1 for count in review_counts
        if count >= BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR
    )
    
    # Determine quality
    if competitors_at_threshold >= BENCHMARK_MEDIUM_MIN_COMPETITORS_AT_THRESHOLD:
        quality = "high"
    elif competitors_at_threshold >= 1:
        quality = "medium"
    elif any(c > 0 for c in review_counts):
        quality = "low"
    else:
        quality = "unavailable"
    
    summary = {
        "total_competitors": total_competitors,
        "competitors_at_threshold": competitors_at_threshold,
        "min_reviews_seen": min(review_counts) if review_counts else 0,
        "max_reviews_seen": max(review_counts) if review_counts else 0,
        "recommended_min_reviews": RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR,
    }
    
    return quality, summary