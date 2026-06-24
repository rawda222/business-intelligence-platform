"""
Preprocessing Service
=====================
Wraps the normalize package + theme_extractor for use inside FastAPI.
"""
from typing import Any

from app.preprocessing.normalize import normalize_raw_data
from app.preprocessing import theme_extractor


def normalize_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw business data using the new modular pipeline.
    """
    return normalize_raw_data(raw_data)


def extract_themes(normalized_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extract themes from normalized data.
    Still uses the legacy theme_extractor for now.
    """
    return theme_extractor.extract_themes_from_normalized(normalized_data)