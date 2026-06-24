"""
Theme Extractor Package
=======================
Production-grade theme extraction for normalized business intelligence data.

Public API:
    extract_themes(data: dict) -> dict
    extract_themes_from_normalized(normalized_data: dict) -> dict

Example:
    from app.preprocessing.theme_extractor import extract_themes_from_normalized
    
    themes = extract_themes_from_normalized(normalized_data)
"""
from app.preprocessing.theme_extractor.pipeline import (
    extract_themes,
    extract_themes_from_normalized,
)

__all__ = [
    "extract_themes",
    "extract_themes_from_normalized",
]