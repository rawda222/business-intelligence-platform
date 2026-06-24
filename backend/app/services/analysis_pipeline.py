"""
Analysis Pipeline
Full End-to-End: Raw Data → Normalize → Themes → SWOT.
"""
from uuid import UUID
from typing import Any

from app.services.preprocessing_service import normalize_data, extract_themes
from app.services.ai_service import generate_swot_report


async def run_full_analysis(
    business_id: UUID,
    business_type: str,
    raw_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Run the complete BI pipeline:
    
    1. Normalize raw business data
    2. Extract themes from normalized data
    3. Generate SWOT report from themes (via Gemini)
    
    Returns a summary with references to stored reports.
    """

    # Step 1: Normalize
    normalized = normalize_data(raw_data)

    # Step 2: Extract themes
    themes = extract_themes(normalized)

    # Step 3: Generate SWOT
    swot_doc = await generate_swot_report(
        business_id=business_id,
        business_type=business_type,
        themes_data=themes,
    )

    return {
        "stages": {
            "normalized": True,
            "themes_extracted": True,
            "swot_generated": True,
        },
        "counts": {
            "themes_total": len(themes.get("themes", [])),
            "reviews_processed": len(
                normalized.get("business_reviews", [])
            ),
            "competitors_processed": len(
                normalized.get("competitors", [])
            ),
        },
        "swot_report_id": str(swot_doc.id),
        "swot_summary": swot_doc.strategic_summary,
        "themes_preview": themes.get("themes", [])[:5],
    }