"""
Strategy Agent v1 - Filtering Package
======================================
Input gating functions that enforce should_feed_strategy_agent
at the Python layer BEFORE any LLM call.
"""
from app.agents.strategy.filtering.eligibility import as_dict, is_eligible
from app.agents.strategy.filtering.input_filter import filter_strategy_inputs

__all__ = [
    "as_dict",
    "is_eligible",
    "filter_strategy_inputs",
]