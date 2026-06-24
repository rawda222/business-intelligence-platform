"""
Normalize - Reviews
===================
Convert raw review dicts (with arbitrary/inconsistent keys) into the
unified review schema.

Unified review schema:
    {
        "review_id": str,
        "entity_name": str,
        "entity_type": "target_business" | "competitor",
        "text": str (original),
        "clean_text": str (cleaned),
        "rating": float | None,
        "language": "ar" | "en" | "mixed" | "unknown",
        "sentiment_hint": "positive" | "negative" | "neutral" | "mixed" | "unknown",
        "category_tags": list[str],
        "is_synthetic": bool,
        "usable_for_analysis": bool,
        "source": str,
    }
"""
import hashlib
import re

from app.preprocessing.normalize.helpers import (
    safe_get,
    extract_text_value,
    to_float,
)
from app.preprocessing.normalize.text_cleaning import clean_text
from app.preprocessing.normalize.language import detect_language
from app.preprocessing.normalize.sentiment import detect_sentiment_hint
from app.preprocessing.normalize.synthetic import is_synthetic_text


def build_review_id(entity_type: str, entity_name: str, index: int, raw_text: str) -> str:
    """
    Build a stable, unique review ID.
    
    Format: {entity_type}_{safe_name}_{index}_{text_hash[:8]}
    """
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', (entity_name or "unknown")).strip("_").lower()
    if not safe_name:
        safe_name = "unknown"
    
    h = hashlib.sha1((raw_text or "").encode("utf-8")).hexdigest()[:8]
    return f"{entity_type}_{safe_name}_{index}_{h}"


def normalize_review(
    raw_review,
    entity_name: str,
    entity_type: str,
    index: int,
    source: str,
    quality_report: dict,
) -> dict:
    """
    Convert a single raw review (dict or string) to the unified schema.
    
    Args:
        raw_review: Raw review data (dict or str)
        entity_name: Business or competitor name
        entity_type: "target_business" or "competitor"
        index: Position in the source list
        source: Source identifier (e.g. "google_reviews")
        quality_report: Quality report to annotate
    
    Returns:
        Normalized review dict
    """
    # Handle case where review is just a raw string
    if not isinstance(raw_review, dict):
        raw_review = {"text": raw_review}
    
    # 1. Extract raw text (handle multi-language dicts)
    raw_text_value = safe_get(raw_review, [
        "text", "review_text", "content", "comment", "body", "message",
    ])
    raw_text = extract_text_value(raw_text_value) or ""
    
    # 2. Clean the text
    cleaned = clean_text(raw_text) or ""
    
    # 3. Extract rating
    rating_value = safe_get(raw_review, [
        "rating", "stars", "score", "star_rating",
    ])
    rating = to_float(rating_value)
    
    # 4. Detect language
    language = detect_language(cleaned)
    
    # 5. Detect sentiment
    predefined_sentiment = safe_get(raw_review, [
        "sentiment", "sentiment_label", "sentiment_hint",
    ])
    sentiment_hint = detect_sentiment_hint(
        text=cleaned,
        rating=rating,
        predefined_sentiment=predefined_sentiment,
    )
    
    # 6. Extract category tags
    category_tags = safe_get(raw_review, ["category_tags", "tags", "categories"]) or []
    if isinstance(category_tags, str):
        category_tags = [category_tags]
    if not isinstance(category_tags, list):
        category_tags = []
    
    # 7. Check if synthetic
    source_synthetic_flag = safe_get(raw_review, ["is_synthetic", "synthetic"])
    is_synthetic = is_synthetic_text(cleaned, source_flag=source_synthetic_flag)
    
    # 8. Build review ID
    review_id = build_review_id(entity_type, entity_name, index, raw_text)
    
    # 9. Determine if usable for analysis
    usable = not is_synthetic and bool(cleaned and cleaned.strip())
    
    # 10. Build unified review
    normalized = {
        "review_id": review_id,
        "entity_name": entity_name,
        "entity_type": entity_type,
        "text": raw_text,
        "clean_text": cleaned,
        "rating": rating,
        "language": language,
        "sentiment_hint": sentiment_hint,
        "category_tags": category_tags,
        "is_synthetic": is_synthetic,
        "usable_for_analysis": usable,
        "source": source,
    }
    
    # 11. Annotate quality report if synthetic
    if is_synthetic:
        quality_report["synthetic_items"].append({
            "review_id": review_id,
            "entity_name": entity_name,
            "reason": "matched_synthetic_marker_or_empty",
        })
    
    return normalized


def normalize_reviews_collection(
    raw_reviews,
    entity_name: str,
    entity_type: str,
    source: str,
    quality_report: dict,
) -> list:
    """
    Normalize a collection of reviews.
    
    raw_reviews may be:
    - a list of review dicts/strings
    - a dict containing a list under common keys (e.g. 'items', 'list',
      'reviews', 'reviews_sample')
    - None / missing
    
    Returns:
        List of normalized review dicts
    """
    if raw_reviews is None:
        return []
    
    # Unwrap if it's a dict containing a list
    if isinstance(raw_reviews, dict):
        for key in ("items", "list", "reviews", "reviews_sample", "data"):
            if key in raw_reviews and isinstance(raw_reviews[key], list):
                raw_reviews = raw_reviews[key]
                break
        else:
            # Couldn't find a list - return empty
            return []
    
    # Ensure it's a list
    if not isinstance(raw_reviews, list):
        return []
    
    # Normalize each review
    normalized = []
    for index, raw_review in enumerate(raw_reviews):
        review = normalize_review(
            raw_review=raw_review,
            entity_name=entity_name,
            entity_type=entity_type,
            index=index,
            source=source,
            quality_report=quality_report,
        )
        normalized.append(review)
    
    return normalized