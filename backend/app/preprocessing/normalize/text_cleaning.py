"""
Normalize - Text Cleaning
=========================
Functions for cleaning and normalizing review text.
"""
import re
import unicodedata

from app.preprocessing.normalize.config import NON_SENTIMENT_SYMBOL_RANGE


def strip_non_sentiment_symbols(text: str) -> str:
    """Remove flags, variation selectors, and decorative symbols."""
    return NON_SENTIMENT_SYMBOL_RANGE.sub("", text)


def normalize_repeated_punctuation(text: str) -> str:
    """Collapse repeated punctuation."""
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'\.{2,3}', '...', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    return text


def normalize_whitespace(text: str) -> str:
    """Normalize unicode and collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_text(raw_text):
    """
    Main text-cleaning pipeline.
    Returns None if input is None.
    """
    if raw_text is None:
        return None
    
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
    
    text = raw_text
    text = normalize_whitespace(text)
    text = normalize_repeated_punctuation(text)
    text = strip_non_sentiment_symbols(text)
    text = text.strip()
    
    return text