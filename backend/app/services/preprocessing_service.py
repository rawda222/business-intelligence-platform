"""
Preprocessing Service
=====================
Wraps the normalize + theme_extractor packages for use inside FastAPI.

Both packages are now modular (Strangler Fig pattern):
- normalize: 13 files
- theme_extractor: 12 files
"""
from typing import Any

from app.preprocessing.normalize import normalize_raw_data
from app.preprocessing.theme_extractor import extract_themes_from_normalized


def normalize_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw business data using the modular normalize package.
    """
    return normalize_raw_data(raw_data)


def extract_themes(normalized_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extract themes using the modular theme_extractor package.
    """
    return extract_themes_from_normalized(normalized_data)