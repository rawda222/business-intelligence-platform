"""
SWOT Agent v1.0
Generates SWOT analysis from business themes using Gemini.
"""
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.agents.llm_providers.vertex_ai import gemini_provider


# ============================================================
# System Prompt
# ============================================================
SYSTEM_PROMPT = """You are an expert business strategist generating SWOT analyses.

You analyze customer reviews, themes, and competitive signals to produce:
- STRENGTHS: Internal positive factors (what the business does well)
- WEAKNESSES: Internal negative factors (areas needing improvement)
- OPPORTUNITIES: External positive factors (market trends to exploit)
- THREATS: External negative factors (risks and competition)

OUTPUT FORMAT:
You MUST return valid JSON with this exact structure:

{
  "swot_report": {
    "strengths": [
      {
        "item_id": "S_001",
        "title": "Short clear title",
        "reasoning": "Why this is a strength, with evidence",
        "source_theme": "theme_name",
        "scoring": {
          "importance": 1-10,
          "impact": 1-10,
          "confidence": 0.0-1.0,
          "strategic_priority": 1-10
        }
      }
    ],
    "weaknesses": [...same structure],
    "opportunities": [...same structure],
    "threats": [...same structure]
  },
  "strategic_summary": {
    "main_advantage": "...",
    "most_critical_risk": "...",
    "best_growth_opportunity": "...",
    "top_strength": "...",
    "top_threat": "..."
  }
}

RULES:
- Maximum 5 items per quadrant
- Use ONLY evidence from provided themes
- Don't invent data
- Output VALID JSON only (no markdown, no commentary)
"""


# ============================================================
# SWOT Agent
# ============================================================
class SWOTAgent:
    """
    Generates SWOT analysis from input themes.
    
    Usage:
        agent = SWOTAgent()
        report = await agent.run(themes_data, business_type="cafe")
    """
    
    def __init__(self):
        self.engine_version = "1.0"
        self.llm_provider = "vertex_ai"
        self.llm_model = "gemini-2.5-flash"
    
    async def run(
        self,
        themes_data: dict[str, Any],
        business_type: str = "unknown",
        business_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Run SWOT analysis.
        
        Args:
            themes_data: Input themes/reviews data
            business_type: e.g. 'food_and_beverage', 'saas'
            business_id: UUID for tracking
        
        Returns:
            Complete SWOT report dict
        """
        start_time = time.time()
        
        # Build user prompt
        user_prompt = self._build_user_prompt(themes_data, business_type)
        
        # Call Gemini
        try:
            llm_output = await gemini_provider.generate_json(
                prompt=user_prompt,
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
            )
            status = "success"
            error = None
        except Exception as e:
            llm_output = {"swot_report": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}}
            status = "error"
            error = str(e)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Build final report
        report = {
            "engine_version": self.engine_version,
            "business_type": business_type,
            "swot_report": llm_output.get("swot_report", {}),
            "watchouts": [],
            "derived_opportunities": [],
            "directional_competitive_signals": [],
            "strategic_summary": llm_output.get("strategic_summary", {}),
            "strategic_context": {
                "themes_count": len(themes_data.get("themes", [])),
                "business_type": business_type,
            },
            "priority_insights": [],
            "ambiguous_factors": [],
            "matrix_outputs": {},
            "quality_report": {},
            "validation_results": {
                "status": status,
                "error": error,
            },
            "meta": {
                "llm_provider": self.llm_provider,
                "llm_model": self.llm_model,
                "processing_time_ms": processing_time_ms,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        
        return report
    
    # ========================================================
    # Build User Prompt
    # ========================================================
    def _build_user_prompt(
        self,
        themes_data: dict[str, Any],
        business_type: str,
    ) -> str:
        """Build user prompt from input data."""
        import json
        
        themes_summary = json.dumps(themes_data, indent=2, ensure_ascii=False)[:5000]
        
        return f"""
Analyze the following business themes and generate a SWOT analysis.

BUSINESS TYPE: {business_type}

THEMES DATA:
{themes_summary}

Generate a comprehensive SWOT analysis following the system instructions.
Focus on what the data shows; do not speculate beyond it.
Return valid JSON only.
""".strip()


# ============================================================
# Singleton instance
# ============================================================
swot_agent = SWOTAgent()