"""
Full BI Pipeline Endpoint
=========================

Reviews -> Normalize -> Themes -> SWOT v7 -> Strategy

Includes:

- Scraper payload adaptation.
- Review normalization.
- Theme extraction.
- Exact Theme Extractor -> SWOT v7 profile mapping.
- Vertex AI enrichment.
- MongoDB persistence.
- Strategy generation.
- JSON file upload support.
"""

import json
from typing import Any, Dict
from uuid import UUID

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from app.agents.strategy import StrategyAgent
from app.agents.swot import (
    LLMProvider,
    SWOTAgent,
)
from app.agents.swot.llm.chain import (
    LLMClientFactory,
)
from app.models.mongo.strategy_report import (
    StrategyReportDocument,
)
from app.models.mongo.swot_report import (
    SWOTReportDocument,
)
from app.preprocessing.normalize.pipeline import (
    normalize_raw_data,
)
from app.preprocessing.scraper_adapter import (
    adapt_scraper_data,
)
from app.preprocessing.theme_extractor.pipeline import (
    extract_themes,
)
from app.services.swot_business_profile_builder import (
    build_swot_business_profile,
)


load_dotenv()


router = APIRouter(
    prefix="/businesses/{business_id}/pipeline",
    tags=["Full Pipeline"],
)


class PipelineInput(BaseModel):
    """Raw business-intelligence pipeline input."""

    raw_data: Dict[str, Any]


def _safe_collection_length(
    value: Any,
) -> int:
    """Return the length of one list-like collection."""

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return len(
            value
        )

    return 0


def _safe_review_count(
    normalized: Dict[str, Any],
) -> int:
    """Return the normalized target-business review count."""

    for key in (
        "business_reviews",
        "normalized_reviews",
        "reviews",
    ):
        value = normalized.get(
            key
        )

        if isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):
            return len(
                value
            )

    return 0


def _safe_non_negative_int(
    value: Any,
) -> int:
    """Convert one value to a non-negative integer."""

    if isinstance(
        value,
        bool,
    ):
        return 0

    try:
        normalized = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        0,
        normalized,
    )


def _competitor_review_counts(
    normalized: Dict[str, Any],
) -> dict[str, int]:
    """Extract deterministic competitor review-count metadata."""

    competitors = normalized.get(
        "competitors",
        [],
    )

    if not isinstance(
        competitors,
        list,
    ):
        return {}

    result: dict[str, int] = {}

    for competitor in competitors:
        if not isinstance(
            competitor,
            dict,
        ):
            continue

        raw_name = competitor.get(
            "name"
        )

        if not isinstance(
            raw_name,
            str,
        ):
            continue

        name = raw_name.strip()

        if not name:
            continue

        declared_count = (
            _safe_non_negative_int(
                competitor.get(
                    "review_count"
                )
            )
        )

        if declared_count == 0:
            declared_count = (
                _safe_collection_length(
                    competitor.get(
                        "reviews_sample"
                    )
                )
            )

        result[name] = declared_count

    return result


# ============================================================
# Full Pipeline: JSON Input
# ============================================================
@router.post("/full")
async def run_full_pipeline(
    business_id: str,
    payload: PipelineInput,
):
    """
    Run the complete BI pipeline for one business.

    The Theme Extractor output is mapped into the exact SWOT v7
    BusinessProfile contract before the SWOT Agent is executed.
    """

    try:
        parsed_business_id = UUID(
            business_id
        )

        # ========================================================
        # Step 0: Adapt scraper data
        # ========================================================
        adapted_raw = adapt_scraper_data(
            payload.raw_data
        )

        # ========================================================
        # Step 1: Normalize review-oriented input
        # ========================================================
        normalized = normalize_raw_data(
            adapted_raw
        )

        # ========================================================
        # Step 2: Extract review themes and signals
        # ========================================================
        themes_output = extract_themes(
            normalized
        )

        # ========================================================
        # Step 3: Build the Vertex AI LLM fallback chain
        # ========================================================
        llm_chain = (
            LLMClientFactory.build_chain(
                preferred=(
                    LLMProvider.VERTEX_AI
                ),
                model="gemini-2.5-flash",
            )
        )

        # ========================================================
        # Step 4: Build exact SWOT v7 input contract
        # ========================================================
        target_review_count = (
            _safe_review_count(
                normalized
            )
        )

        competitor_review_counts = (
            _competitor_review_counts(
                normalized
            )
        )

        profile = (
            build_swot_business_profile(
                business_name=(
                    adapted_raw.get(
                        "business_name",
                        "Unknown",
                    )
                ),
                business_type=(
                    adapted_raw.get(
                        "business_type",
                        "unknown",
                    )
                ),
                themes_output=(
                    themes_output
                ),
                target_review_count=(
                    target_review_count
                ),
                competitor_review_counts=(
                    competitor_review_counts
                ),
            )
        )

        # ========================================================
        # Step 5: Generate SWOT v7
        # ========================================================
        swot_agent = SWOTAgent(
            provider=(
                LLMProvider.VERTEX_AI
            ),
            model="gemini-2.5-flash",
            dry_run=False,
        )

        swot_agent.chain = llm_chain

        swot_output = swot_agent.run(
            profile
        )

        swot_dict = (
            swot_output.model_dump()
        )

        # ========================================================
        # Step 6: Persist SWOT
        # ========================================================
        swot_doc = SWOTReportDocument(
            business_id=(
                parsed_business_id
            ),
            engine_version=(
                swot_dict.get(
                    "engine_version",
                    "7.0",
                )
            ),
            business_type=(
                swot_dict.get(
                    "business_type",
                    "unknown",
                )
            ),
            swot_report=(
                swot_dict.get(
                    "swot_report",
                    {},
                )
            ),
            watchouts=(
                swot_dict.get(
                    "watchouts",
                    [],
                )
            ),
            derived_opportunities=(
                swot_dict.get(
                    "derived_opportunities",
                    [],
                )
            ),
            directional_competitive_signals=(
                swot_dict.get(
                    "directional_competitive_signals",
                    [],
                )
            ),
            strategic_summary=(
                swot_dict.get(
                    "strategic_summary",
                    {},
                )
            ),
            strategic_context=(
                swot_dict.get(
                    "strategic_context",
                    {},
                )
            ),
            priority_insights=(
                swot_dict.get(
                    "priority_insights",
                    [],
                )
            ),
            ambiguous_factors=(
                swot_dict.get(
                    "ambiguous_factors",
                    [],
                )
            ),
            matrix_outputs=(
                swot_dict.get(
                    "matrix_outputs",
                    {},
                )
            ),
            quality_report=(
                swot_dict.get(
                    "quality_report",
                    {},
                )
            ),
            validation_results=(
                swot_dict.get(
                    "validation_results",
                    {},
                )
            ),
            meta=(
                swot_dict.get(
                    "meta",
                    {},
                )
            ),
        )

        await swot_doc.insert()

        # ========================================================
        # Step 7: Generate Strategy from the saved SWOT output
        # ========================================================
        strategy_agent = StrategyAgent(
            llm_chain=llm_chain,
            dry_run=False,
        )

        strategy_output = (
            strategy_agent.run(
                swot_dict
            )
        )

        strategy_dict = (
            strategy_output.model_dump()
        )

        # ========================================================
        # Step 8: Persist Strategy
        # ========================================================
        strategy_doc = (
            StrategyReportDocument(
                business_id=(
                    parsed_business_id
                ),
                source_swot_id=(
                    swot_doc.report_id
                ),
                engine_version=(
                    strategy_dict.get(
                        "engine_version",
                        "1.0",
                    )
                ),
                meta=(
                    strategy_dict.get(
                        "meta",
                        {},
                    )
                ),
                tows_synthesis=(
                    strategy_dict.get(
                        "tows_matrix",
                        {},
                    )
                ),
                initiatives=(
                    strategy_dict.get(
                        "priority_action_plan",
                        [],
                    )
                ),
                strategic_recommendations={
                    "strategic_posture": (
                        strategy_dict.get(
                            "strategic_posture"
                        )
                    ),
                    "posture_rationale": (
                        strategy_dict.get(
                            "posture_rationale"
                        )
                    ),
                    "campaign_brief_feed": (
                        strategy_dict.get(
                            "campaign_brief_feed",
                            [],
                        )
                    ),
                    "resource_assessment": (
                        strategy_dict.get(
                            "resource_assessment",
                            [],
                        )
                    ),
                },
                execution_notes=(
                    strategy_dict.get(
                        "strategy_quality_report",
                        {},
                    )
                ),
            )
        )

        await strategy_doc.insert()

        # ========================================================
        # Final response
        # ========================================================
        return {
            "business_id": business_id,
            "persisted": {
                "swot_mongo_id": (
                    str(
                        swot_doc.id
                    )
                ),
                "strategy_mongo_id": (
                    str(
                        strategy_doc.id
                    )
                ),
                "swot_report_id": (
                    str(
                        swot_doc.report_id
                    )
                ),
                "strategy_report_id": (
                    str(
                        strategy_doc.report_id
                    )
                ),
            },
            "normalize_summary": {
                "review_count": (
                    target_review_count
                ),
                "available_keys": list(
                    normalized.keys()
                ),
            },
            "themes_summary": {
                "themes_count": len(
                    themes_output.get(
                        "themes",
                        [],
                    )
                ),
                "positive_signals_count": len(
                    themes_output.get(
                        "positive_signals",
                        [],
                    )
                ),
                "negative_signals_count": len(
                    themes_output.get(
                        "negative_signals",
                        [],
                    )
                ),
                "opportunity_signals_count": len(
                    themes_output.get(
                        "opportunity_signals",
                        [],
                    )
                ),
                "threat_signals_count": len(
                    themes_output.get(
                        "threat_signals",
                        [],
                    )
                ),
            },
            "swot_profile_summary": {
                "themes_count": len(
                    profile.themes
                ),
                "target_review_count": (
                    profile
                    .reviews_summary
                    .target_review_count
                    if profile.reviews_summary
                    is not None
                    else 0
                ),
                "competitor_review_counts": (
                    profile
                    .reviews_summary
                    .competitor_review_counts
                    if profile.reviews_summary
                    is not None
                    else {}
                ),
            },
            "swot": swot_dict,
            "strategy": strategy_dict,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(
                error
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        ) from error


# ============================================================
# Upload Scraper File
# ============================================================
@router.post("/upload")
async def run_pipeline_from_file(
    business_id: str,
    file: UploadFile = File(...),
):
    """Parse one uploaded JSON file and run the full BI pipeline."""

    try:
        content = await file.read()

        raw_data = json.loads(
            content
        )

        if not isinstance(
            raw_data,
            dict,
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "The uploaded JSON must contain "
                    "an object at the root."
                ),
            )

        payload = PipelineInput(
            raw_data=raw_data
        )

        return await run_full_pipeline(
            business_id,
            payload,
        )

    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid JSON: "
                f"{error}"
            ),
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        ) from error