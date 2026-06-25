"""
Strategy Agent v1 - Helper Utilities
=====================================
Small utility functions used across the agent.
"""
from typing import Any, Set


def collect_valid_item_ids(filtered: dict) -> Set[str]:
    """
    Build set of all valid SWOT item_ids that strategies can reference.
    """
    ids = set()

    for quad in ("strengths", "weaknesses", "opportunities", "threats"):
        for item in filtered.get(quad, []):
            if item.get("item_id"):
                ids.add(item["item_id"])

    for item in filtered.get("derived_opportunities", []):
        if item.get("item_id"):
            ids.add(item["item_id"])

    for sig in filtered.get("directional_competitive_signals", []):
        if sig.get("signal_id"):
            ids.add(sig["signal_id"])

    return ids