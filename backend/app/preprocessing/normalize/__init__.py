"""
Normalize Package
=================
Production-grade data normalization for business intelligence datasets.

Public API:
    normalize_raw_data(raw_data: dict) -> dict
        Main entry point. Normalizes raw business data into a unified schema.

Example:
    from app.preprocessing.normalize import normalize_raw_data
    
    result = normalize_raw_data({
        "business_identity": {"name": "My Cafe"},
        "business_reviews": [...],
        "competitors": [...],
    })
"""
from app.preprocessing.normalize.pipeline import normalize_raw_data

__all__ = ["normalize_raw_data"]