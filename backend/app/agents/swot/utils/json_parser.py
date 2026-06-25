"""
SWOT Agent v7 - Safe JSON Parser
=================================
Parse LLM responses that may contain markdown fences.
"""
import json
import re
import logging
from typing import Any, Dict


logger = logging.getLogger("swot_agent_v7")


def safe_parse_json(text: str) -> Dict[str, Any]:
    """
    Parse JSON safely, attempting to strip markdown fences if present.
    
    Handles LLM outputs that may include:
    - ```json ... ```
    - ```\n...\n```
    - Plain JSON
    - JSON embedded in prose
    
    Returns empty dict on failure (never raises).
    """
    if not text:
        return {}
    
    raw = text.strip()
    
    # Strip markdown json fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    
    # Try direct JSON parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    # Fallback: find first { ... } block
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning("Failed to parse LLM JSON; returning empty dict.")
    return {}