"""
SWOT Agent v7 - Stage 4: LLM Enrichment
========================================
Call LLM chain to enrich SWOT analysis with intelligent reasoning.
"""
import logging
from typing import List, Optional, Tuple

from app.agents.swot.schemas.input import BusinessProfile, ReviewTheme
from app.agents.swot.schemas.llm import LLMSWOTOutput
from app.agents.swot.llm.base import LLMClient
from app.agents.swot.llm.chain import call_llm_chain
from app.agents.swot.prompts.system import SYSTEM_PROMPT
from app.agents.swot.prompts.user import build_user_prompt
from app.agents.swot.utils.json_parser import safe_parse_json
from app.agents.swot.stages.stage3_rule_based import generate_rule_based_swot


logger = logging.getLogger("swot_agent_v7")


def _normalize_llm_output(parsed: dict) -> dict:
    """
    Make sure the parsed LLM output matches the LLMSWOTOutput schema.

    Handles common formats Gemini returns:

    Format A:
        { "swot_report": {...}, "strategic_summary": {...} }

    Format B:
        { "strengths": [...], "weaknesses": [...], ... }

    Format C:
        { "swot": {...} }
    """
    if not isinstance(parsed, dict):
        return {}

    if "swot_report" in parsed:
        return parsed

    if "swot" in parsed and isinstance(parsed["swot"], dict):
        return {"swot_report": parsed["swot"]}

    if any(
        k in parsed
        for k in ("strengths", "weaknesses", "opportunities", "threats")
    ):
        return {
            "swot_report": {
                "strengths": parsed.get("strengths", []),
                "weaknesses": parsed.get("weaknesses", []),
                "opportunities": parsed.get("opportunities", []),
                "threats": parsed.get("threats", []),
            },
            "strategic_summary": parsed.get("strategic_summary", {}),
        }

    return parsed


def enrich_with_llm(
    profile: BusinessProfile,
    kept_themes: List[ReviewTheme],
    chain: List[LLMClient],
    benchmark_quality: str,
    benchmark_summary: dict,
) -> Tuple[LLMSWOTOutput, str, str, bool]:
    """
    Call LLM to enrich SWOT analysis.

    Falls back to rule-based generation if all LLM providers fail.
    """

    # 🔥 Extract reviews from profile (if attached)
    raw_reviews = getattr(profile, "raw_reviews", None) or []

    # 🔥 Build LLM user prompt WITH raw reviews
    user_prompt = build_user_prompt(
        profile=profile,
        kept_themes=kept_themes,
        benchmark_quality=benchmark_quality,
        benchmark_summary=benchmark_summary,
        raw_reviews=raw_reviews,
    )

    if chain:
        logger.info(
            f"[Stage 4] Calling LLM chain ({len(chain)} providers) | "
            f"reviews={len(raw_reviews)} themes={len(kept_themes)}"
        )

        response_text, successful_client = call_llm_chain(
            chain=chain,
            system=SYSTEM_PROMPT,
            user=user_prompt,
        )

        if response_text and successful_client:
            try:
                # 🔥 Debug raw Gemini response
                logger.warning("=" * 80)
                logger.warning("[Stage 4] RAW LLM RESPONSE START")
                logger.warning(response_text[:2000])
                logger.warning("[Stage 4] RAW LLM RESPONSE END")
                logger.warning("=" * 80)

                parsed = safe_parse_json(response_text)
                parsed = _normalize_llm_output(parsed)

                if parsed:
                    output = LLMSWOTOutput(**parsed)

                    strengths_count = (
                        len(output.swot_report.strengths)
                        if output.swot_report else 0
                    )
                    logger.info(
                        f"[Stage 4] LLM success: "
                        f"{successful_client.provider_name} "
                        f"(strengths={strengths_count})"
                    )

                    return (
                        output,
                        successful_client.provider_name,
                        getattr(successful_client, "model", "unknown"),
                        False,
                    )
            except Exception as exc:
                logger.warning(f"[Stage 4] LLM output parsing failed: {exc}")

    logger.warning("[Stage 4] All LLM providers failed - using rule-based fallback")
    output = generate_rule_based_swot(profile, benchmark_quality)
    return output, "rule_based", "n/a", True