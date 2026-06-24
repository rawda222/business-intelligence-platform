"""
Preprocessing Service
Wraps normalize.py + theme_extractor.py for use inside FastAPI.
"""
from typing import Any

from app.preprocessing import normalize
from app.preprocessing import theme_extractor


def normalize_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw business data (clean + structure).
    Returns the normalized dataset.
    """
    return normalize.normalize_raw_data(raw_data)


def extract_themes(normalized_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extract themes from normalized data.
    Returns the theme analysis dict.
    """
    return theme_extractor.extract_themes_from_normalized(normalized_data)