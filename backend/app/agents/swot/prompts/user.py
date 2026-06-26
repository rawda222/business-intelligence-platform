"""
SWOT Agent v7 - User Prompt Builder
====================================
Now ENFORCES that Gemini returns evidence_refs (real quotes per item).
"""

import json
from typing import Any, Dict, List

from app.agents.swot.schemas.input import BusinessProfile, ReviewTheme


def build_user_prompt(
    profile: BusinessProfile,
    kept_themes: List[ReviewTheme],
    benchmark_quality: str,
    benchmark_summary: Dict[str, Any],
    raw_reviews: List[str] = None,
) -> str:
    """
    Build the LLM user prompt including:
    - Business info
    - Themes
    - Reviews
    - Strict format with evidence_refs
    """

    themes_payload = []
    for t in kept_themes:
        themes_payload.append({
            "theme_category": t.theme_category,
            "entity_type": t.entity_type,
            "frequency": t.frequency,
            "sentiment_balance": {
                "positive": t.sentiment_balance.positive,
                "negative": t.sentiment_balance.negative,
                "neutral": t.sentiment_balance.neutral,
                "mixed": t.sentiment_balance.mixed,
            },
        })

    prompt_data = {
        "business_name": profile.business_name,
        "business_type": profile.business_type,
        "benchmark_quality": benchmark_quality,
        "benchmark_summary": benchmark_summary,
        "themes": themes_payload,
    }

    data_json = json.dumps(prompt_data, indent=2, ensure_ascii=False)

    reviews_block = ""
    if raw_reviews:
        joined = "\n".join(f"- {r}" for r in raw_reviews if r)
        reviews_block = f"\n[CUSTOMER REVIEWS]\n{joined}\n"

    user_prompt = f"""You are an AI Business Strategist.

Analyze the following business and produce a SWOT analysis.

BUSINESS DATA:
{data_json}
{reviews_block}

RULES (MANDATORY):
1. Read the CUSTOMER REVIEWS carefully.
2. Generate SWOT (strengths, weaknesses, opportunities, threats).
3. EACH SWOT item MUST contain:
   - title
   - reasoning (1-3 sentences)
   - source_theme
   - quadrant
   - tags (1-5 short tags)
   - scoring (importance, impact, confidence)
   - evidence_refs (MAX 3 SHORT EXACT QUOTES from the reviews above)

4. evidence_refs MUST contain real quotes from the reviews. 
   NEVER paraphrase. NEVER write empty arrays unless absolutely no review supports the item.

5. Reasoning MUST be supported by the evidence_refs.

STRICT JSON FORMAT:
{{
  "swot_report": {{
    "strengths": [
      {{
        "title": "...",
        "reasoning": "...",
        "source_theme": "...",
        "quadrant": "strengths",
        "tags": ["..."],
        "scoring": {{"importance": 8, "impact": 8, "confidence": 0.9}},
        "evidence_refs": [
          "Exact quote 1",
          "Exact quote 2"
        ]
      }}
    ],
    "weaknesses": [...],
    "opportunities": [...],
    "threats": [...]
  }},
  "strategic_summary": {{
    "main_advantage": "...",
    "most_critical_risk": "...",
    "best_growth_opportunity": "..."
  }}
}}

Return STRICT JSON only — no comments, no commentary.
"""

    return user_prompt