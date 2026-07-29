"""
Analysis Pipeline
=================

Raw Data
-> Normalize
-> Semantic Themes
-> Ready for Grounded SWOT Workflow
"""

from typing import Any
from uuid import UUID

from app.services.preprocessing_service import (
    extract_themes,
    normalize_data,
)


async def run_full_analysis(
    business_id: UUID,
    business_type: str,
    raw_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Run preprocessing and semantic theme extraction.

    Confirmed SWOT generation is handled exclusively by the
    Grounded SWOT proposal and approval workflow.
    """

    normalized = normalize_data(
        raw_data
    )

    themes = extract_themes(
        normalized
    )

    theme_records = themes.get(
        "themes",
        [],
    )

    if not theme_records:
        raise ValueError(
            "No validated semantic themes were produced."
        )

    return {
        "business_id": str(business_id),
        "business_type": business_type,
        "stages": {
            "normalized": True,
            "themes_extracted": True,
            "swot_generated": False,
        },
        "counts": {
            "themes_total": len(
                theme_records
            ),
            "reviews_processed": len(
                normalized.get(
                    "business_reviews",
                    [],
                )
            ),
            "competitors_processed": len(
                normalized.get(
                    "competitors",
                    [],
                )
            ),
            "positive_signals": len(
                themes.get(
                    "positive_signals",
                    [],
                )
            ),
            "negative_signals": len(
                themes.get(
                    "negative_signals",
                    [],
                )
            ),
            "opportunity_signals": len(
                themes.get(
                    "opportunity_signals",
                    [],
                )
            ),
            "threat_signals": len(
                themes.get(
                    "threat_signals",
                    [],
                )
            ),
        },
        "normalized_data": normalized,
        "themes_data": themes,
        "next_step": {
            "workflow": "grounded_swot_proposal",
            "endpoint": (
                "/api/v1/businesses/"
                f"{business_id}/swot/proposals"
            ),
            "requires_human_approval": True,
        },
    }