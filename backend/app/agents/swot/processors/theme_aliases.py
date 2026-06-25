"""
SWOT Agent v7 - Theme Aliases
==============================
Map semantically similar theme categories to canonical names.

Example: 'staff_behavior' + 'service_speed' -> 'service'
"""
from typing import Dict


THEME_ALIAS_MAP: Dict[str, str] = {
    # Service family
    "staff_behavior": "service",
    "service_speed": "service",
    "customer_experience": "service",
}


def get_canonical_category(theme_category: str) -> str:
    """
    Get the canonical category for a theme.
    
    Returns the alias mapping if exists, otherwise returns the input unchanged.
    """
    return THEME_ALIAS_MAP.get(theme_category, theme_category)