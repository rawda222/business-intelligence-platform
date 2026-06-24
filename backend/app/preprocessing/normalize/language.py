"""
Normalize - Language Detection
==============================
Simple heuristic language detection based on character ranges.

Supported languages:
- ar: Arabic
- en: English
- mixed: Both Arabic and English present
- unknown: Cannot determine
"""
from app.preprocessing.normalize.config import ARABIC_RANGE, LATIN_RANGE


def detect_language(text):
    """
    Detect the dominant language of a text using character ranges.
    
    Returns:
        'ar'      - if mostly Arabic characters
        'en'      - if mostly Latin characters
        'mixed'   - if both significantly present
        'unknown' - if neither dominant or text is empty
    """
    if not text or not isinstance(text, str) or text.strip() == "":
        return "unknown"
    
    # Count Arabic and Latin characters
    arabic_count = len(ARABIC_RANGE.findall(text))
    latin_count = len(LATIN_RANGE.findall(text))
    
    # If neither is present, return unknown
    if arabic_count == 0 and latin_count == 0:
        return "unknown"
    
    # If only one is present, return that
    if arabic_count > 0 and latin_count == 0:
        return "ar"
    if latin_count > 0 and arabic_count == 0:
        return "en"
    
    # Both present - check dominance
    total = arabic_count + latin_count
    arabic_ratio = arabic_count / total
    latin_ratio = latin_count / total
    
    # If one dominates (>70%), return it
    if arabic_ratio > 0.7:
        return "ar"
    if latin_ratio > 0.7:
        return "en"
    
    # Otherwise, mixed
    return "mixed"