"""
Strategy Agent v1 - Eligibility Helpers
========================================
Helper functions for checking if SWOT items are eligible
to feed into the Strategy Agent.

Enforces should_feed_strategy_agent gating at the Python layer
BEFORE the LLM sees any data.
"""
from typing import Any, Dict


def as_dict(item: Any) -> Dict[str, Any]:
    """
    Coerce a Pydantic v2 model or dict to a plain dict.
    
    Safe fallback for unknown types - returns empty dict.
    """
    if hasattr(item, "model_dump"):
        return item.model_dump()
    
    if isinstance(item, dict):
        return item
    
    # Best-effort fallback
    try:
        return dict(item)
    except Exception:
        return {}


def is_eligible(item: Any) -> bool:
    """
    An item is eligible if its should_feed_strategy_agent flag is true.
    
    This is the core gating function - items where this flag is False
    will NEVER reach the Strategy Agent (or its LLM).
    """
    d = as_dict(item)
    return bool(d.get("should_feed_strategy_agent", False))