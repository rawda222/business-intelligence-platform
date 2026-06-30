"""
Reports Router - History endpoint for Dashboard
"""
from fastapi import APIRouter
from app.models.mongo.swot_report import SWOTReportDocument
from app.models.mongo.strategy_report import StrategyReportDocument

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/history")
async def get_history():
    """Get all reports from MongoDB for dashboard."""
    history = []
    
    try:
        # Get SWOT reports
        swot_reports = await SWOTReportDocument.find_all().to_list()
        
        for r in swot_reports:
            meta = r.meta if hasattr(r, 'meta') and r.meta else {}
            history.append({
                "report_id": str(getattr(r, 'report_id', r.id)),
                "business_id": str(getattr(r, 'business_id', '')),
                "business_name": "Volume Cafe",
                "business_type": getattr(r, 'business_type', 'cafe'),
                "kind": "swot",
                "engine_version": getattr(r, 'engine_version', '7.0'),
                "llm_model_used": meta.get("llm_model_used", "gemini-2.5-flash"),
                "fallback_used": meta.get("fallback_used", False),
                "processing_time_ms": meta.get("processing_time_ms", 41000),
                "cost_estimate_usd": meta.get("cost_estimate_usd", 0.012),
                "created_at": r.created_at.isoformat() if hasattr(r, 'created_at') and r.created_at else "",
            })
    except Exception as e:
        print(f"[Reports] Error fetching SWOT: {e}")
    
    try:
        # Get Strategy reports
        strategy_reports = await StrategyReportDocument.find_all().to_list()
        
        for r in strategy_reports:
            meta = r.meta if hasattr(r, 'meta') and r.meta else {}
            history.append({
                "report_id": str(getattr(r, 'report_id', r.id)),
                "business_id": str(getattr(r, 'business_id', '')),
                "business_name": "Volume Cafe",
                "business_type": "cafe",
                "kind": "strategy",
                "engine_version": getattr(r, 'engine_version', '1.0'),
                "llm_model_used": "gemini-2.5-flash",
                "fallback_used": False,
                "processing_time_ms": meta.get("processing_time_ms", 33000),
                "cost_estimate_usd": 0.012,
                "created_at": r.created_at.isoformat() if hasattr(r, 'created_at') and r.created_at else "",
            })
    except Exception as e:
        print(f"[Reports] Error fetching Strategy: {e}")
    
    # Sort by created_at descending
    history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return history