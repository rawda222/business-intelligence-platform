"""
Strategy Agent v1 - User Prompt Builder
========================================
Constructs the user prompt sent to the LLM for strategy generation.
"""
import json
from typing import Any, Dict


def build_strategy_user_prompt(filtered_inputs: Dict[str, Any]) -> str:
    """
    Construct the user prompt for the Strategy Agent.
    
    Receives the already-filtered SWOT inputs (only eligible items).
    The LLM sees ONLY what filter_strategy_inputs() allowed through.
    
    Args:
        filtered_inputs: Output of filter_strategy_inputs()
    
    Returns:
        Formatted prompt string
    """
    # Pretty-print the filtered inputs as JSON
    data_json = json.dumps(filtered_inputs, indent=2, ensure_ascii=False)
    
    # Build context section
    business_type = filtered_inputs.get("business_type", "unknown")
    validation_status = filtered_inputs.get("validation_status", "UNKNOWN")
    benchmark_quality = filtered_inputs.get("benchmark_quality", "unavailable")
    
    counts = {
        "strengths": len(filtered_inputs.get("strengths", [])),
        "weaknesses": len(filtered_inputs.get("weaknesses", [])),
        "opportunities": len(filtered_inputs.get("opportunities", [])),
        "threats": len(filtered_inputs.get("threats", [])),
        "derived_opportunities": len(filtered_inputs.get("derived_opportunities", [])),
        "directional_signals": len(filtered_inputs.get("directional_competitive_signals", [])),
    }
    
    user_prompt = f"""
Generate strategic synthesis for the following business.

CONTEXT:
- Business type: {business_type}
- SWOT validation status: {validation_status}
- Benchmark data quality: {benchmark_quality}

INPUT COUNTS:
- Strengths: {counts['strengths']}
- Weaknesses: {counts['weaknesses']}
- Opportunities: {counts['opportunities']}
- Threats: {counts['threats']}
- Derived Opportunities: {counts['derived_opportunities']}
- Directional Signals: {counts['directional_signals']}

FULL SWOT DATA (already filtered for strategy eligibility):
{data_json}

INSTRUCTIONS:
1. Analyze the SWOT inputs above
2. Generate strategies for each TOWS cell (SO, ST, WO, WT)
3. Use ONLY the item_ids that appear in the input data above
4. Classify the strategic_posture based on the dominant pattern
5. Apply confidence inheritance: weakest anchor wins
6. Return STRICT JSON matching the schema in the system prompt

Output JSON only.
"""
    
    return user_prompt.strip()