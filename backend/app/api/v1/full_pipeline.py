"""
Full BI Pipeline Endpoint
==========================
Reviews → Normalize → Themes → SWOT v7 → Strategy
With MongoDB persistence + Scraper Adapter + Upload endpoint
"""
from dotenv import load_dotenv
load_dotenv()

import json
from uuid import UUID
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

# Pipeline modules
from app.preprocessing.normalize.pipeline import normalize_raw_data
from app.preprocessing.theme_extractor.pipeline import extract_themes
from app.preprocessing.scraper_adapter import adapt_scraper_data

# AI agents
from app.agents.swot import (
    SWOTAgent,
    LLMProvider,
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)
from app.agents.strategy import StrategyAgent
from app.agents.swot.llm.chain import LLMClientFactory

# MongoDB Documents
from app.models.mongo.swot_report import SWOTReportDocument
from app.models.mongo.strategy_report import StrategyReportDocument


router = APIRouter(
    prefix="/businesses/{business_id}/pipeline",
    tags=["Full Pipeline"],
)


class PipelineInput(BaseModel):
    raw_data: Dict[str, Any]


def _safe_review_count(normalized: Dict[str, Any]) -> int:
    if "business_reviews" in normalized:
        return len(normalized["business_reviews"])
    if "normalized_reviews" in normalized:
        return len(normalized["normalized_reviews"])
    if "reviews" in normalized:
        return len(normalized["reviews"])
    return 0


def _extract_review_texts(payload_data: Dict[str, Any]) -> List[str]:
    out = []
    for r in payload_data.get("business_reviews", []):
        if isinstance(r, dict):
            text = r.get("text") or ""
            if text:
                out.append(text)
        elif isinstance(r, str):
            out.append(r)
    return out


# =========================================================
# Full Pipeline (JSON input)
# =========================================================
@router.post("/full")
async def run_full_pipeline(business_id: str, payload: PipelineInput):
    try:
        # STEP 0: Adapt scraper data
        adapted_raw = adapt_scraper_data(payload.raw_data)

        # STEP 1: Normalize
        normalized = normalize_raw_data(adapted_raw)

        # STEP 2: Themes
        themes_output = extract_themes(normalized)

        # STEP 3: LLM Chain
        llm_chain = LLMClientFactory.build_chain(
            preferred=LLMProvider.VERTEX_AI,
            model="gemini-2.5-flash",
        )

        # STEP 4: Build Themes
        review_texts = _extract_review_texts(adapted_raw)

        themes_list = []
        for t in themes_output.get("themes", []):
            sb = t.get("sentiment_balance", {}) or {}

            pos = sb.get("positive", 0)
            neg = sb.get("negative", 0)
            neu = sb.get("neutral", 0)
            mix = sb.get("mixed", 0)

            if pos + neg + neu + mix == 0:
                pos = max(1, t.get("frequency", 1))

            themes_list.append(
                ReviewTheme(
                    theme_category=t.get("theme_category", "unknown"),
                    entity_type=t.get("entity_type", "target_business"),
                    frequency=t.get("frequency", 1),
                    sentiment_balance=SentimentBalance(
                        positive=pos,
                        negative=neg,
                        neutral=neu,
                        mixed=mix,
                    ),
                )
            )

        # STEP 5: Profile
        profile = BusinessProfile(
            business_name=adapted_raw.get("business_name", "Unknown"),
            business_type=adapted_raw.get("business_type", "cafe"),
            themes=themes_list,
        )
        object.__setattr__(profile, "raw_reviews", review_texts)

        # STEP 6: SWOT
        swot_agent = SWOTAgent(
            provider=LLMProvider.VERTEX_AI,
            model="gemini-2.5-flash",
            dry_run=False,
        )
        swot_agent.chain = llm_chain
        swot_agent.llm_chain = llm_chain

        swot_output = swot_agent.run(profile)
        swot_dict = swot_output.model_dump()

        # STEP 7: Save SWOT
        swot_doc = SWOTReportDocument(
            business_id=UUID(business_id),
            engine_version=swot_dict.get("engine_version", "7.0"),
            business_type=swot_dict.get("business_type", "unknown"),
            swot_report=swot_dict.get("swot_report", {}),
            watchouts=swot_dict.get("watchouts", []),
            derived_opportunities=swot_dict.get("derived_opportunities", []),
            directional_competitive_signals=swot_dict.get("directional_competitive_signals", []),
            strategic_summary=swot_dict.get("strategic_summary", {}),
            strategic_context=swot_dict.get("strategic_context", {}),
            priority_insights=swot_dict.get("priority_insights", []),
            ambiguous_factors=swot_dict.get("ambiguous_factors", []),
            matrix_outputs=swot_dict.get("matrix_outputs", {}),
            quality_report=swot_dict.get("quality_report", {}),
            validation_results=swot_dict.get("validation_results", {}),
            meta=swot_dict.get("meta", {}),
        )
        await swot_doc.insert()

        # STEP 8: Strategy
        strategy_agent = StrategyAgent(
            llm_chain=llm_chain,
            dry_run=False,
        )
        strategy_output = strategy_agent.run(swot_dict)
        strategy_dict = strategy_output.model_dump()

        # STEP 9: Save Strategy
        strategy_doc = StrategyReportDocument(
            business_id=UUID(business_id),
            source_swot_id=swot_doc.report_id,
            engine_version=strategy_dict.get("engine_version", "1.0"),
            meta=strategy_dict.get("meta", {}),
            tows_synthesis=strategy_dict.get("tows_matrix", {}),
            initiatives=strategy_dict.get("priority_action_plan", []),
            strategic_recommendations={
                "strategic_posture": strategy_dict.get("strategic_posture"),
                "posture_rationale": strategy_dict.get("posture_rationale"),
                "campaign_brief_feed": strategy_dict.get("campaign_brief_feed", []),
                "resource_assessment": strategy_dict.get("resource_assessment", []),
            },
            execution_notes=strategy_dict.get("strategy_quality_report", {}),
        )
        await strategy_doc.insert()

        # FINAL
        return {
            "business_id": business_id,
            "persisted": {
                "swot_mongo_id": str(swot_doc.id),
                "strategy_mongo_id": str(strategy_doc.id),
                "swot_report_id": str(swot_doc.report_id),
                "strategy_report_id": str(strategy_doc.report_id),
            },
            "normalize_summary": {
                "review_count": _safe_review_count(normalized),
                "available_keys": list(normalized.keys()),
                "raw_review_count_input": len(review_texts),
            },
            "themes_summary": {
                "themes_count": len(themes_output.get("themes", [])),
            },
            "swot": swot_dict,
            "strategy": strategy_dict,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# Upload Scraper File
# =========================================================
@router.post("/upload")
async def run_pipeline_from_file(business_id: str, file: UploadFile = File(...)):
    """
    Upload a scraper JSON file directly.
    The system parses it and runs the full BI pipeline.
    """
    try:
        content = await file.read()
        raw_data = json.loads(content)

        payload = PipelineInput(raw_data=raw_data)
        return await run_full_pipeline(business_id, payload)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))