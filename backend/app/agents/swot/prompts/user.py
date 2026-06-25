"""
SWOT Agent v7 - User Prompt Builder
====================================
Builds the user prompt sent to LLM.

Now supports raw customer reviews directly.
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
    Build the LLM user prompt using:
    - Business info
    - Themes
    - Raw customer reviews (to give Gemini real evidence)
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
            "target_score": t.target_score,
            "competitor_score": t.competitor_score,
            "performance_gap": t.performance_gap,
            "mention_count": len(t.mentions),
        })

    prompt_data = {
        "business_name": profile.business_name,
        "business_type": profile.business_type,
        "benchmark_quality": benchmark_quality,
        "benchmark_summary": benchmark_summary,
        "themes": themes_payload,
    }

    data_json = json.dumps(prompt_data, indent=2, ensure_ascii=False)

    # 🔥 Reviews block
    reviews_block = ""
    if raw_reviews:
        joined = "\n".join(f"- {r}" for r in raw_reviews if r)
        reviews_block = f"\nCUSTOMER REVIEWS:\n{joined}\n"

    user_prompt = f"""Analyze the following business and produce a SWOT analysis.

BUSINESS DATA:
{data_json}
{reviews_block}
INSTRUCTIONS:
1. Read the CUSTOMER REVIEWS carefully.
2. Cross-reference with themes and sentiment balances.
3. For high-positive themes → propose a Strength with reasoning grounded in the reviews.
4. For high-negative themes → propose a Weakness with reasoning grounded in the reviews.
5. Identify Opportunities (growth signals implied in reviews).
6. Identify Threats (risks implied in reviews).
7. Use the exact theme_category as 'source_theme' for each item.
8. Provide reasoning grounded in actual review wording.

OUTPUT STRICT JSON FORMAT:
{{
  "swot_report": {{
    "strengths": [...],
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

Return STRICT JSON only.
"""

    return user_prompt