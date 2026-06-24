"""
Theme Extractor - Detection
===========================
Detect predefined and dynamic themes in reviews.
"""
import re
from collections import Counter
from typing import Any, Dict, List

from app.preprocessing.theme_extractor.config import (
    MIN_FREQUENCY_FOR_DYNAMIC_THEME,
)
from app.preprocessing.theme_extractor.taxonomy import (
    PREDEFINED_THEMES,
    PREDEFINED_PATTERNS,
    normalize_category_tag,
)
from app.preprocessing.theme_extractor.reviews import get_review_text


# ---------------------------------------------------------------------------
# Stop words for dynamic theme discovery
# ---------------------------------------------------------------------------
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "his",
    "of", "in", "on", "at", "for", "to", "from", "with", "by", "this",
    "that", "these", "those", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "can", "just",
    "very", "really", "so", "too", "more", "less", "than", "as", "if",
    "when", "where", "why", "how", "what", "which", "who", "all", "any",
    "some", "no", "not", "only", "own", "same", "such", "then", "now",
    "here", "there", "again", "also", "even", "after", "before", "while",
    "us", "me", "him", "her", "them", "our", "their",
}


def detect_theme_categories_for_review(review: Dict[str, Any]) -> List[str]:
    """
    Detect which predefined themes apply to a single review.
    
    Two sources:
    1. Explicit category_tags that map to known themes
    2. Keyword/phrase matches in the cleaned text
    """
    detected = set()
    
    # 1. Check explicit category tags
    category_tags = review.get("category_tags") or []
    if isinstance(category_tags, list):
        for tag in category_tags:
            theme_key = normalize_category_tag(tag)
            if theme_key:
                detected.add(theme_key)
    
    # 2. Check keyword matches in text
    text = get_review_text(review)
    if text:
        for theme_key, pattern in PREDEFINED_PATTERNS.items():
            if pattern.search(text):
                detected.add(theme_key)
    
    return sorted(detected)


def discover_dynamic_themes(
    reviews: List[Dict[str, Any]],
    matched_theme_map: Dict[str, List[str]],
    min_frequency: int = MIN_FREQUENCY_FOR_DYNAMIC_THEME,
) -> Dict[str, List[str]]:
    """
    Find recurring meaningful words in reviews that didn't match predefined themes.
    
    Returns:
        Dict mapping emerging theme keys (e.g. 'emerging_pasta') to
        list of review_ids that mention them.
    """
    word_to_reviews: Dict[str, List[str]] = {}
    
    for review in reviews:
        review_id = review.get("review_id")
        if not review_id:
            continue
        
        # Skip reviews that already matched predefined themes
        if review_id in matched_theme_map and matched_theme_map[review_id]:
            continue
        
        text = get_review_text(review).lower()
        if not text:
            continue
        
        # Tokenize into words
        words = re.findall(r'[a-zA-Z\u0600-\u06FF]{3,}', text)
        
        # Filter out stop words
        words = [w for w in words if w not in _STOP_WORDS]
        
        # Count unique words per review (avoid duplicates)
        unique_words = set(words)
        for word in unique_words:
            if word not in word_to_reviews:
                word_to_reviews[word] = []
            word_to_reviews[word].append(review_id)
    
    # Keep only words appearing in min_frequency+ reviews
    dynamic_themes = {
        f"emerging_{word}": review_ids
        for word, review_ids in word_to_reviews.items()
        if len(review_ids) >= min_frequency
    }
    
    return dynamic_themes