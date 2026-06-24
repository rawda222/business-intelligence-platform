"""
Theme Extractor - Review Helpers
================================
Functions for collecting and filtering reviews.
"""
from typing import Any, Dict, List


def collect_all_reviews(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Gather all reviews (target business + competitors) into a flat list.
    
    Each review is expected to follow the unified schema from normalize.
    """
    all_reviews: List[Dict[str, Any]] = []
    
    # Target business reviews
    business_reviews = data.get("business_reviews") or []
    if isinstance(business_reviews, list):
        all_reviews.extend(business_reviews)
    
    # Competitor reviews
    competitors = data.get("competitors") or []
    if isinstance(competitors, list):
        for comp in competitors:
            if isinstance(comp, dict):
                sample = comp.get("reviews_sample") or []
                if isinstance(sample, list):
                    all_reviews.extend(sample)
    
    return all_reviews


def get_review_text(review: Dict[str, Any]) -> str:
    """
    Get the cleaned text of a review, falling back to raw text.
    """
    text = review.get("clean_text")
    if not text:
        text = review.get("text")
    if not isinstance(text, str):
        return ""
    return text


def is_usable(review: Dict[str, Any]) -> bool:
    """
    Determine if a review is usable for theme extraction.
    
    Filters out:
    - Synthetic reviews (flagged)
    - Reviews with usable_for_analysis=False
    - Empty text
    """
    if review.get("is_synthetic") is True:
        return False
    
    usable_flag = review.get("usable_for_analysis")
    if usable_flag is False:
        return False
    
    text = get_review_text(review)
    return bool(text and text.strip())