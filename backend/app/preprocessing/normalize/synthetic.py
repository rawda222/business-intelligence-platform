"""
Normalize - Synthetic Text Detection
====================================
Detect placeholder, sample, or auto-generated review text.

These reviews should typically be excluded from analysis.
"""
from app.preprocessing.normalize.config import SYNTHETIC_MARKERS


def is_synthetic_text(text, source_flag=None):
    """
    Check if text appears to be a placeholder, synthetic, or sample
    rather than a real review.
    
    Args:
        text: Review text (or None)
        source_flag: Source-provided is_synthetic flag (overrides detection)
    
    Returns:
        True if text appears synthetic, False otherwise
    """
    # 1. Explicit source flag wins
    if source_flag is True:
        return True
    
    # 2. Empty / None text
    if not text or not isinstance(text, str):
        return False
    
    text_lower = text.lower().strip()
    
    # 3. Very short text (less than 3 characters)
    if len(text_lower) < 3:
        return True
    
    # 4. Match against synthetic markers
    for marker in SYNTHETIC_MARKERS:
        if marker in text_lower:
            return True
    
    # 5. Repeated characters (e.g. "aaaa", "test test test")
    if len(text_lower) > 5:
        # If 70%+ of chars are the same, it's likely synthetic
        most_common_char_count = max(text_lower.count(c) for c in set(text_lower))
        if most_common_char_count / len(text_lower) > 0.7:
            return True
    
    return False