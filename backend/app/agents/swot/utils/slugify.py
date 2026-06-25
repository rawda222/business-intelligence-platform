"""
SWOT Agent v7 - Slugify Utility
================================
Convert text to URL-safe identifiers.
"""
import re


def slugify(text: str) -> str:
    """
    Slugify a string for use in item_ids.
    
    Examples:
        "Food Quality" -> "food_quality"
        "Customer Service!" -> "customer_service"
        "" -> "item"
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_").lower()
    return s or "item"