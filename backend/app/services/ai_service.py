"""
AI Service
Orchestrates AI agents and stores reports in MongoDB.
"""
from uuid import UUID
from typing import Any

from app.agents.swot_agent import swot_agent
from app.models.mongo.swot_report import SWOTReportDocument


# ============================================================
# Generate SWOT Report
# ============================================================
async def generate_swot_report(
    business_id: UUID,
    business_type: str,
    themes_data: dict[str, Any],
) -> SWOTReportDocument:
    """
    Generate a SWOT report and save it to MongoDB.
    
    Args:
        business_id: UUID of the business
        business_type: e.g. 'food_and_beverage'
        themes_data: Input themes/reviews data
    
    Returns:
        Saved SWOTReportDocument
    """
    # 1. Run SWOT agent
    report_data = await swot_agent.run(
        themes_data=themes_data,
        business_type=business_type,
        business_id=business_id,
    )
    
    # 2. Build document
    document = SWOTReportDocument(
        business_id=business_id,
        engine_version=report_data["engine_version"],
        business_type=report_data["business_type"],
        swot_report=report_data["swot_report"],
        watchouts=report_data["watchouts"],
        derived_opportunities=report_data["derived_opportunities"],
        directional_competitive_signals=report_data["directional_competitive_signals"],
        strategic_summary=report_data["strategic_summary"],
        strategic_context=report_data["strategic_context"],
        priority_insights=report_data["priority_insights"],
        ambiguous_factors=report_data["ambiguous_factors"],
        matrix_outputs=report_data["matrix_outputs"],
        quality_report=report_data["quality_report"],
        validation_results=report_data["validation_results"],
        meta=report_data["meta"],
    )
    
    # 3. Save to MongoDB
    await document.insert()
    
    return document


# ============================================================
# Get Latest SWOT Report
# ============================================================
async def get_latest_swot_report(
    business_id: UUID,
) -> SWOTReportDocument | None:
    """
    Get the most recent SWOT report for a business.
    """
    return await SWOTReportDocument.find_one(
        SWOTReportDocument.business_id == business_id,
        sort=[("created_at", -1)],
    )


# ============================================================
# List SWOT Reports
# ============================================================
async def list_swot_reports(
    business_id: UUID,
    limit: int = 10,
) -> list[SWOTReportDocument]:
    """
    List recent SWOT reports for a business.
    """
    return await SWOTReportDocument.find(
        SWOTReportDocument.business_id == business_id,
        sort=[("created_at", -1)],
    ).limit(limit).to_list()
