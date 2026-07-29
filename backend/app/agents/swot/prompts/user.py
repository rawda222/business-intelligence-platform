"""
SWOT Agent v7 - Grounded User Prompt Builder

Builds a source-aware prompt from:

- Aggregated customer-voice themes.
- Deterministic brand-trend candidates.
- Allowed evidence references.
- Observed source coverage.
- Analysis and data-quality warnings.

Evidence references are stable IDs, not raw quotes.
Representative quotes are provided separately as context.
"""

import json
from typing import Any, Dict, List

from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
)


def _theme_payload(
    theme: ReviewTheme,
) -> dict[str, Any]:
    """Serialize one evidence-backed customer theme."""

    return {
        "theme_category": (
            theme.theme_category
        ),
        "entity_type": (
            theme.entity_type
        ),
        "frequency": (
            theme.frequency
        ),
        "sentiment_balance": {
            "positive": (
                theme
                .sentiment_balance
                .positive
            ),
            "negative": (
                theme
                .sentiment_balance
                .negative
            ),
            "neutral": (
                theme
                .sentiment_balance
                .neutral
            ),
            "mixed": (
                theme
                .sentiment_balance
                .mixed
            ),
        },
        "confidence_score": (
            theme.confidence_score
        ),
        "requires_manual_review": (
            theme.requires_manual_review
        ),

        "source_platforms": list(
            theme.source_platforms
        ),
        "representative_quotes": list(
            theme.representative_quotes[
                :3
            ]
        ),
        "evidence_refs": list(
            theme.evidence_refs
        ),
        "target_score": (
            theme.target_score
        ),
        "competitor_score": (
            theme.competitor_score
        ),
        "performance_gap": (
            theme.performance_gap
        ),
    }


def build_user_prompt(
    profile: BusinessProfile,
    kept_themes: List[ReviewTheme],
    benchmark_quality: str,
    benchmark_summary: Dict[str, Any],
    raw_reviews: List[str] | None = None,
) -> str:
    """
    Build a grounded SWOT synthesis prompt.

    raw_reviews remains accepted for backward compatibility, but
    raw review text is not included. Aggregated representative
    quotes and stable evidence IDs are used instead.
    """

    del raw_reviews

    themes_payload = [
        _theme_payload(
            theme
        )
        for theme in kept_themes
    ]

    prompt_data = {
        "business": {
            "business_name": (
                profile.business_name
            ),
            "business_type": (
                profile.business_type
            ),
        },
        "customer_voice_themes": (
            themes_payload
        ),
        "customer_voice_signals": {
            "positive_signals": (
                profile.positive_signals
            ),
            "negative_signals": (
                profile.negative_signals
            ),
            "opportunity_signals": (
                profile.opportunity_signals
            ),
            "threat_signals": (
                profile.threat_signals
            ),
            "comparison_summary": (
                profile.comparison_summary
            ),
        },
        "brand_trend_candidates": (
            profile.trend_candidates
        ),
        "benchmark": {
            "quality": benchmark_quality,
            "summary": benchmark_summary,
        },
        "source_coverage": (
            profile.source_coverage
        ),
        "allowed_evidence_references": (
            profile
            .allowed_evidence_references
        ),
        "analysis_warnings": (
            profile.analysis_warnings
        ),
    }

    data_json = json.dumps(
        prompt_data,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    return f"""
You are generating an evidence-grounded SWOT analysis.

GROUNDING DATA:
{data_json}

MANDATORY EVIDENCE RULES:

1. Use only the supplied customer_voice_themes and
   brand_trend_candidates.

2. evidence_refs are stable IDs. Copy each ID exactly from
   allowed_evidence_references.

3. Never put quotes, paraphrases, invented IDs, URLs, or source
   names inside evidence_refs.

4. Representative quotes are context only. They may support the
   reasoning, but they are not evidence IDs.


5. Never invent metrics, frequencies, ratings, sources, customer
   opinions, competitors, market conditions, or dates.

6. A data gap is not a Weakness, Threat, Strength, or Opportunity.

7. A supporting_signal may provide context but must not become a
   standalone SWOT item.

8. Brand-owned publishing activity is not customer sentiment.

9. Strengths and Weaknesses must be grounded in target-business
   customer themes or eligible deterministic trend candidates.

10. Opportunities and Threats require comparative evidence,
    benchmark evidence, or an explicitly eligible trend candidate.
    If that evidence is absent, return no item for that quadrant.

11. Use exact theme_category values for customer-theme
    source_theme.

12. For a trend-backed item, source_theme must equal the exact
    candidate_id supplied in brand_trend_candidates. Do not add,
    remove, or repeat any prefix.

13. If evidence is insufficient, omit the item. Do not fill
    quadrants merely to produce a balanced matrix.

EACH SWOT ITEM MUST CONTAIN:

- title
- reasoning
- source_theme
- quadrant
- tags
- scoring:
  - importance
  - impact
  - confidence
- evidence_refs
- frequency
14. Any customer theme with requires_manual_review=true is an
    unverified signal. Do not use it in a confirmed SWOT quadrant
    or strategic_summary.

15. If an unverified signal must be acknowledged, omit it from the
    confirmed SWOT and leave it for the human-review workflow.

16. A high confidence_score on a manual-review theme reflects
    confidence in classification only. It does not verify the
    underlying customer allegation.

STRICT JSON FORMAT:

{{
  "swot_report": {{
    "strengths": [
      {{
        "title": "Specific evidence-backed title",
        "reasoning": "Reasoning grounded only in supplied evidence.",
        "source_theme": "exact_theme_category_or_trend:candidate_id",
        "quadrant": "strengths",
        "tags": ["short_tag"],
        "scoring": {{
          "importance": 8.0,
          "impact": 7.0,
          "confidence": 0.85
        }},
        "evidence_refs": [
          "google_maps:review:example"
        ],
        "frequency": 10
      }}
    ],
    "weaknesses": [],
    "opportunities": [],
    "threats": []
  }},
  "strategic_summary": {{
    "main_advantage": "",
    "most_critical_risk": "",
    "best_growth_opportunity": ""
  }}
}}

Return strict JSON only.
""".strip()