"""
Normalize - Sentiment Detection
===============================
Lightweight heuristic sentiment detection for review text.

Priority order:
1. Predefined sentiment label from source (if available)
2. Rating-based inference (if rating present)
3. Keyword matching (EN + AR word lists)
4. Fallback to 'unknown'
"""
from app.preprocessing.normalize.config import (
    POSITIVE_WORDS_EN,
    NEGATIVE_WORDS_EN,
    POSITIVE_WORDS_AR,
    NEGATIVE_WORDS_AR,
)


# Sentiment label normalization mapping
SENTIMENT_LABEL_MAPPING = {
    "positive": "positive",
    "pos": "positive",
    "negative": "negative",
    "neg": "negative",
    "neutral": "neutral",
    "mixed": "mixed",
    "unknown": "unknown",
}


def detect_sentiment_hint(text, rating=None, predefined_sentiment=None):
    """
    Lightweight, heuristic sentiment detection.
    
    Priority:
    1. If a predefined sentiment label exists in the source data, use it.
    2. Otherwise, derive from rating if available.
    3. Otherwise, derive from keyword matching (EN + AR).
    4. Fallback to 'unknown'.
    
    Args:
        text: Review text (or None)
        rating: Numeric rating (e.g. 1-5) or None
        predefined_sentiment: Source-provided sentiment label or None
    
    Returns:
        One of: 'positive', 'negative', 'neutral', 'mixed', 'unknown'
    """
    # 1. Predefined sentiment from source
    if predefined_sentiment and isinstance(predefined_sentiment, str):
        norm = predefined_sentiment.strip().lower()
        if norm in SENTIMENT_LABEL_MAPPING:
            return SENTIMENT_LABEL_MAPPING[norm]
    
    # 2. Rating-based inference
    if rating is not None:
        try:
            r = float(rating)
            if r >= 4.0:
                return "positive"
            if r <= 2.0:
                return "negative"
            if 2.0 < r < 4.0:
                return "neutral"
        except (ValueError, TypeError):
            pass
    
    # 3. Keyword matching
    if text and isinstance(text, str):
        sentiment = _detect_by_keywords(text)
        if sentiment != "unknown":
            return sentiment
    
    # 4. Fallback
    return "unknown"


def _detect_by_keywords(text: str) -> str:
    """
    Detect sentiment using keyword matching against EN + AR word lists.
    """
    text_lower = text.lower()
    
    # Count positive and negative word matches
    pos_count = 0
    neg_count = 0
    
    # English (whole-word matching via simple split)
    words = set(text_lower.split())
    pos_count += len(words & POSITIVE_WORDS_EN)
    neg_count += len(words & NEGATIVE_WORDS_EN)
    
    # Arabic (substring matching since words can blend)
    for word in POSITIVE_WORDS_AR:
        if word in text:
            pos_count += 1
    for word in NEGATIVE_WORDS_AR:
        if word in text:
            neg_count += 1
    
    # Decide based on counts
    if pos_count > 0 and neg_count > 0:
        return "mixed"
    if pos_count > 0:
        return "positive"
    if neg_count > 0:
        return "negative"
    
    return "unknown"