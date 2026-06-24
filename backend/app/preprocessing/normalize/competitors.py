"""
Normalize - Competitors
=======================
Normalize competitor entries from raw input.

Each competitor has:
- name
- review_count
- reviews_sample (normalized list)
"""
from app.preprocessing.normalize.helpers import safe_get, to_int
from app.preprocessing.normalize.reviews import normalize_reviews_collection


def normalize_competitor(raw_competitor, index: int, quality_report: dict) -> dict | None:
    """
    Normalize a single competitor entry.
    
    Args:
        raw_competitor: Raw competitor dict
        index: Position in competitors list
        quality_report: Quality report to annotate
    
    Returns:
        Normalized competitor dict, or None if invalid
    """
    if not isinstance(raw_competitor, dict):
        quality_report["mismatches"].append({
            "section": "competitors",
            "index": index,
            "issue": "competitor entry is not an object",
        })
        return None
    
    # Extract name
    name = safe_get(raw_competitor, [
        "name", "competitor_name", "business_name", "title",
    ])
    
    if not name:
        quality_report["mismatches"].append({
            "section": "competitors",
            "index": index,
            "issue": "competitor missing name",
        })
        name = f"unknown_competitor_{index}"
    
    # Extract review count
    review_count = to_int(safe_get(raw_competitor, [
        "review_count", "total_reviews", "reviews_count",
    ])) or 0
    
    # Normalize reviews_sample
    raw_reviews = safe_get(raw_competitor, [
        "reviews_sample", "reviews", "sample_reviews",
    ])
    
    reviews_sample = normalize_reviews_collection(
        raw_reviews=raw_reviews,
        entity_name=name,
        entity_type="competitor",
        source=safe_get(raw_competitor, ["source"]) or "competitor_data",
        quality_report=quality_report,
    )
    
    # If declared review_count is 0 but we have actual reviews, use the actual count
    if review_count == 0 and reviews_sample:
        review_count = len(reviews_sample)
    
    return {
        "name": name,
        "review_count": review_count,
        "rating_avg": safe_get(raw_competitor, ["rating", "avg_rating", "rating_avg"]),
        "location": safe_get(raw_competitor, ["location", "address"]),
        "website": safe_get(raw_competitor, ["website", "url"]),
        "reviews_sample": reviews_sample,
    }


def normalize_competitors(raw_data: dict, quality_report: dict) -> list:
    """
    Normalize all competitors from raw input.
    
    Args:
        raw_data: Original raw input dict
        quality_report: Quality report to annotate
    
    Returns:
        List of normalized competitor dicts
    """
    raw_competitors = safe_get(raw_data, ["competitors"])
    
    if raw_competitors is None:
        return []
    
    if not isinstance(raw_competitors, list):
        quality_report["mismatches"].append({
            "section": "competitors",
            "issue": "competitors is not a list",
        })
        return []
    
    normalized = []
    for index, raw_competitor in enumerate(raw_competitors):
        comp = normalize_competitor(raw_competitor, index, quality_report)
        if comp is not None:
            normalized.append(comp)
    
    return normalized