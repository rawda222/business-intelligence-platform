"""
Strategy Agent v1 - Input Filtering
====================================
Extract only the fields the Strategy Agent is authorized to use.

This enforces the "downstream gating" pattern at the Python layer:
- Only items with should_feed_strategy_agent=True pass through
- Validation status and benchmark quality are preserved
- The LLM sees ONLY filtered, eligible data
"""
import logging
from typing import Any, Dict, List

from app.agents.strategy.filtering.eligibility import as_dict, is_eligible


logger = logging.getLogger("strategy_agent_v1")


def filter_strategy_inputs(swot_output: Any) -> Dict[str, Any]:
    """
    Extract only the fields the Strategy Agent is authorized to use.
    
    Filters:
    - SWOT quadrants (strengths, weaknesses, opportunities, threats)
      → only items with should_feed_strategy_agent=True
    - Derived opportunities → only eligible items
    - Directional competitive signals → only eligible items
    
    Preserves:
    - business_type
    - validation_status
    - benchmark_quality
    - watchouts (read-only metadata for posture inference)
    
    Args:
        swot_output: SWOTOutput dict or model
    
    Returns:
        Filtered dict ready for the LLM
    """
    sd = as_dict(swot_output)
    
    swot_report = sd.get("swot_report", {}) or {}
    
    # Filter each SWOT quadrant
    filtered = {
        "business_type": sd.get("business_type", "unknown"),
        "validation_status": (
            sd.get("validation_results", {}).get("overall_status", "UNKNOWN")
        ),
        "benchmark_quality": (
            sd.get("strategic_context", {}).get("benchmark_quality", "unavailable")
        ),
        "strengths": _filter_items(swot_report.get("strengths", [])),
        "weaknesses": _filter_items(swot_report.get("weaknesses", [])),
        "opportunities": _filter_items(swot_report.get("opportunities", [])),
        "threats": _filter_items(swot_report.get("threats", [])),
        "derived_opportunities": _filter_items(sd.get("derived_opportunities", [])),
        "directional_competitive_signals": _filter_items(
            sd.get("directional_competitive_signals", [])
        ),
        # Watchouts are read-only metadata (NOT consumed by LLM)
        "watchout_count": len(sd.get("watchouts", []) or []),
    }
    
    # Log gating stats
    total_in = sum(
        len(swot_report.get(q, []) or [])
        for q in ("strengths", "weaknesses", "opportunities", "threats")
    )
    total_out = sum(
        len(filtered[q])
        for q in ("strengths", "weaknesses", "opportunities", "threats")
    )
    
    logger.info(
        f"[Filter] Filtered SWOT inputs: "
        f"{total_in} input items -> {total_out} eligible items"
    )
    
    return filtered


def _filter_items(items: List[Any]) -> List[Dict[str, Any]]:
    """
    Filter a list of items to only those marked eligible.
    
    Returns dicts (not models) for LLM consumption.
    """
    if not items:
        return []
    
    eligible = []
    for item in items:
        if is_eligible(item):
            eligible.append(as_dict(item))
    
    return eligible