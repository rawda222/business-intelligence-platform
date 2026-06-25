"""
Full BI Pipeline Endpoint
==========================
Reviews → Normalize → Themes → SWOT v7 → Strategy
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List

# Pipeline modules
from app.preprocessing.normalize.pipeline import normalize_raw_data
from app.preprocessing.theme_extractor.pipeline import extract_themes

# AI agents
from app.agents.swot import (
    SWOTAgent,
    LLMProvider,
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)
from app.agents.strategy import StrategyAgent

# LLM chain (shared)
from app.agents.swot.llm.chain import LLMClientFactory


router = APIRouter(
    prefix="/businesses/{business_id}/pipeline",
    tags=["Full Pipeline"],
)


class PipelineInput(BaseModel):
    raw_data: Dict[str, Any]


def _safe_review_count(normalized: Dict[str, Any]) -> int:
    """Find normalized reviews count from any common key."""
    if "business_reviews" in normalized:
        return len(normalized["business_reviews"])
    if "normalized_reviews" in normalized:
        return len(normalized["normalized_reviews"])
    if "reviews" in normalized:
        return len(normalized["reviews"])
    return 0


def _extract_review_texts(payload_data: Dict[str, Any]) -> List[str]:
    """Extract clean text list from any review structure."""
    out = []
    for r in payload_data.get("business_reviews", []):
        if isinstance(r, dict):
            text = r.get("text") or ""
            if text:
                out.append(text)
        elif isinstance(r, str):
            out.append(r)
    return out


@router.post("/full")
def run_full_pipeline(business_id: str, payload: PipelineInput):
    """
    Run the FULL BI pipeline:
    Normalize → Themes → SWOT v7 → Strategy
    """
    try:
        # ============================
        # STEP 1: Normalize
        # ============================
        normalized = normalize_raw_data(payload.raw_data)

        # ============================
        # STEP 2: Theme Extraction
        # ============================
        themes_output = extract_themes(normalized)

        # ============================
        # STEP 3: Build LLM Chain ONCE
        # ============================
        llm_chain = LLMClientFactory.build_chain(
            preferred=LLMProvider.VERTEX_AI,
            model="gemini-2.5-flash",
        )

        # ============================
        # STEP 4: Extract Reviews & Themes
        # ============================
        review_texts = _extract_review_texts(payload.raw_data)

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

        # ============================
        # STEP 5: Build Profile
        # ============================
        profile = BusinessProfile(
            business_name=payload.raw_data.get("business_name", "Unknown"),
            business_type=payload.raw_data.get("business_type", "cafe"),
            themes=themes_list,
        )

        # 🔥 Inject reviews safely (Pydantic v2 friendly)
        object.__setattr__(profile, "raw_reviews", review_texts)

        # ============================
        # STEP 6: SWOT v7 (Gemini)
        # ============================
        swot_agent = SWOTAgent(
            provider=LLMProvider.VERTEX_AI,
            model="gemini-2.5-flash",
            dry_run=False,
        )

        # Force shared chain
        swot_agent.chain = llm_chain
        swot_agent.llm_chain = llm_chain

        swot_output = swot_agent.run(profile)

        # ============================
        # STEP 7: Strategy Agent (Gemini)
        # ============================
        strategy_agent = StrategyAgent(
            llm_chain=llm_chain,
            dry_run=False,
        )

        strategy_output = strategy_agent.run(swot_output.model_dump())

        # ============================
        # FINAL RESPONSE
        # ============================
        return {
            "business_id": business_id,
            "normalize_summary": {
                "review_count": _safe_review_count(normalized),
                "available_keys": list(normalized.keys()),
                "raw_review_count_input": len(review_texts),
            },
            "themes_summary": {
                "themes_count": len(themes_output.get("themes", [])),
            },
            "swot": swot_output.model_dump(),
            "strategy": strategy_output.model_dump(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))