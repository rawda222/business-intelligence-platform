"""
Normalize - Generic Helpers
===========================
Defensive utility functions for safe data access and type coercion.

Used across all normalize submodules.
"""
import re


def safe_get(d, keys, default=None):
    """
    Defensive lookup across multiple possible key names.
    
    Args:
        d: Source dict
        keys: A single key (str) or list/tuple of candidate key names
        default: Value to return if not found
    
    Returns:
        The first non-empty value found, or default.
        Note: 0 and False are preserved as valid values.
    """
    if d is None or not isinstance(d, dict):
        return default
    
    # Normalize keys to a list
    if isinstance(keys, str):
        keys = [keys]
    
    for key in keys:
        if key in d:
            value = d[key]
            # Treat None and empty strings as missing
            if value is not None and value != "":
                return value
    
    return default


def extract_text_value(value):
    """
    Unwrap multi-language text values stored as dicts.
    
    Some sources store review text as:
        {'ar': '...'} or {'en': '...', 'ar': '...'}
    
    Sometimes serialized as a Python-repr string like:
        "{'ar': '...'}"
    
    This helper returns the underlying text string
    (preferring 'ar', then 'en', then any other value).
    """
    if value is None:
        return None
    
    # If it's already a string, check if it's a stringified dict
    if isinstance(value, str):
        # Try to detect stringified dict like "{'ar': '...'}"
        if value.startswith("{") and value.endswith("}"):
            try:
                import ast
                parsed = ast.literal_eval(value)
                if isinstance(parsed, dict):
                    value = parsed
            except (ValueError, SyntaxError):
                return value
        else:
            return value
    
    # If it's a dict, unwrap it
    if isinstance(value, dict):
        # Prefer Arabic, then English, then any
        for lang in ("ar", "en"):
            if lang in value and value[lang]:
                return str(value[lang])
        # Fallback: first non-empty value
        for v in value.values():
            if v:
                return str(v)
        return None
    
    return str(value) if value else None


def is_empty(value):
    """
    Check if a value should be considered empty.
    
    Returns True for None, empty strings, empty lists, empty dicts.
    """
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def to_float(value):
    """
    Safely convert a value to float.
    
    Handles strings with extra characters (e.g. "$12.50", "4.5 stars").
    Returns None if conversion is not possible.
    """
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        # Strip non-numeric characters except dots and minus signs
        s = re.sub(r'[^\d.-]', '', s)
        if s in ("", "-", "."):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def to_int(value):
    """
    Safely convert a value to int.
    
    Uses to_float internally, then rounds.
    Returns None if conversion is not possible.
    """
    f = to_float(value)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, TypeError):
        return None
    