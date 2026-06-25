"""
SWOT Agent v7 - Main Pipeline (Orchestrator)
=============================================
Top-level SWOTAgent class that runs the 10-stage pipeline end to end.
"""
import logging
import time
from typing import Optional

from app.agents.swot.config import (
    ENGINE_VERSION,
    COST_ESTIMATE_USD,
    EVIDENCE_DISPLAY_CAP,
)
from app.agents.swot.enums import LLMProvider, ClaimStrength
from app.agents.swot.schemas.input import BusinessProfile
from app.agents.swot.schemas.output import (
    SWOTOutput,
    SWOTReport,
    SWOTItem,
    SWOTScoring,
    EvidenceSummary,
    StrategicContext,
    ValidationResults,
    EngineMeta,
)
from app.agents.swot.utils.slugify import slugify
from app.agents.swot.processors.scoring import (
    normalize_frequency,
    compute_sentiment_performance,
    compute_strategic_priority,
)
from app.agents.swot.processors.benchmark import assess_benchmark_quality
from app.agents.swot.llm.chain import LLMClientFactory
from app.agents.swot.stages.stage1_validation import validate_review_themes
from app.agents.swot.stages.stage2_merging import (
    normalize_and_merge_similar_themes,
    merge_themes_by_category,
)
from app.agents.swot.stages.stage4_llm_enrichment import enrich_with_llm
from app.agents.swot.stages.stage5_shadow_routing import route_shadows_to_watchouts
from app.agents.swot.stages.stage6_quality_checks import run_quality_checks
from app.agents.swot.stages.stage7_strategic import build_strategic_summary
from app.agents.swot.stages.stage8_signals import (
    build_directional_signals,
    build_derived_opportunities,
)
from app.agents.swot.stages.stage9_dedup import detect_semantic_overlaps
from app.agents.swot.stages.stage10_validation import validate_swot_output


logger = logging.getLogger("swot_agent_v7")


class SWOTAgent:
    """
    Top-level orchestrator: runs the 10-stage pipeline end to end.

    Usage:
        agent = SWOTAgent(provider=LLMProvider.AUTO, model=None)
        output = agent.run(profile)
    """

    def __init__(
        self,
        provider=LLMProvider.AUTO,
        model=None,
        dry_run=False,
    ):
        self.provider = provider
        self.model = model
        self.dry_run = dry_run
        self.chain = []

        if not dry_run:
            self.chain = LLMClientFactory.build_chain(
                preferred=provider,
                model=model,
            )

        logger.info(
            f"[SWOTAgent v{ENGINE_VERSION}] Initialized: "
            f"provider={provider.value}, chain_size={len(self.chain)}, "
            f"dry_run={dry_run}"
        )

    def run(self, profile: BusinessProfile) -> SWOTOutput:
        """
        Run the full 10-stage SWOT pipeline.

        Args:
            profile: BusinessProfile with themes from upstream stages.

        Returns:
            SWOTOutput with complete analysis.
        """
        start_time = time.time()

        # =========================================================
        # Stage 1: Theme Validation
        # =========================================================
        kept_themes, filtered_count = validate_review_themes(profile.themes)

        # =========================================================
        # Stage 2: Semantic Merging
        # =========================================================
        merged_themes = normalize_and_merge_similar_themes(kept_themes)
        themes_by_category = merge_themes_by_category(merged_themes)

        # =========================================================
        # Benchmark Assessment
        # =========================================================
        competitor_review_counts = {}
        if profile.reviews_summary:
            competitor_review_counts = profile.reviews_summary.competitor_review_counts

        benchmark_quality, benchmark_summary = assess_benchmark_quality(
            competitor_review_counts
        )

        # =========================================================
        # Stage 4: LLM Enrichment (with fallback to rule-based)
        # =========================================================
        llm_output, provider_used, model_used, fallback_used = enrich_with_llm(
            profile=profile,
            kept_themes=merged_themes,
            chain=self.chain if not self.dry_run else [],
            benchmark_quality=benchmark_quality,
            benchmark_summary=benchmark_summary,
        )

        # =========================================================
        # Convert LLM output -> SWOTItems (with scoring)
        # =========================================================
        swot_report = self._enrich_items(
            llm_output,
            themes_by_category,
            benchmark_quality,
        )

        # =========================================================
        # Stage 5: Shadow Routing
        # =========================================================
        confirmed_weaknesses, watchouts = route_shadows_to_watchouts(
            swot_report.weaknesses,
            themes_by_category,
        )
        swot_report.weaknesses = confirmed_weaknesses

        # =========================================================
        # Stage 8: Build derived opportunities & signals
        # =========================================================
        derived_opportunities = build_derived_opportunities(swot_report.strengths)
        directional_signals = build_directional_signals(
            merged_themes,
            benchmark_quality,
            competitor_review_counts,
        )

        # =========================================================
        # Stage 6: Quality Checks
        # =========================================================
        quality_report = run_quality_checks(swot_report, benchmark_quality)

        # =========================================================
        # Stage 9: Cross-Quadrant Deduplication
        # =========================================================
        detect_semantic_overlaps(swot_report, quality_report)

        # =========================================================
        # Stage 7: Strategic Summary
        # =========================================================
        strategic_summary = build_strategic_summary(
            swot_report=swot_report,
            watchouts=watchouts,
            derived_opportunities=derived_opportunities,
            directional_signals=directional_signals,
            benchmark_quality=benchmark_quality,
        )

        # =========================================================
        # Strategic Context
        # =========================================================
        strategic_context = StrategicContext(
            quadrant_counts={
                "strengths": len(swot_report.strengths),
                "weaknesses": len(swot_report.weaknesses),
                "opportunities": len(swot_report.opportunities),
                "threats": len(swot_report.threats),
            },
            benchmark_quality=benchmark_quality,
            benchmark_summary=benchmark_summary,
            low_benchmark_items=[
                item.item_id
                for q in ("strengths", "weaknesses", "opportunities", "threats")
                for item in getattr(swot_report, q)
                if item.low_benchmark_quality
            ],
            watchout_items=[w.watchout_id for w in watchouts],
            shadow_weakness_items=[
                item.item_id for item in swot_report.weaknesses if item.is_shadow
            ],
        )

        # =========================================================
        # Build initial output
        # =========================================================
        meta = EngineMeta(
            engine_version=ENGINE_VERSION,
            llm_provider_used=provider_used,
            llm_model_used=model_used,
            fallback_used=fallback_used,
            total_themes=len(profile.themes),
            filtered_themes=filtered_count,
            low_confidence_count=len(quality_report.low_confidence_items),
            processing_time_ms=int((time.time() - start_time) * 1000),
            dry_run=self.dry_run,
            cost_estimate_usd=COST_ESTIMATE_USD.get(provider_used, 0.0),
        )

        output = SWOTOutput(
            business_type=profile.business_type or "unknown",
            engine_version=ENGINE_VERSION,
            swot_report=swot_report,
            watchouts=watchouts,
            derived_opportunities=derived_opportunities,
            directional_competitive_signals=directional_signals,
            strategic_summary=strategic_summary,
            strategic_context=strategic_context,
            quality_report=quality_report,
            meta=meta,
        )

        # =========================================================
        # Stage 10: Validation Tests
        # =========================================================
        violations = validate_swot_output(output.model_dump())
        output.validation_results = ValidationResults(
            tests_passed=8 - len(violations),
            tests_failed=len(violations),
            violations=violations,
            overall_status="PASS" if not violations else "WARN",
        )

        logger.info(
            f"[SWOTAgent] Pipeline complete in {meta.processing_time_ms}ms. "
            f"Items: S={len(swot_report.strengths)}, "
            f"W={len(swot_report.weaknesses)}, "
            f"O={len(swot_report.opportunities)}, "
            f"T={len(swot_report.threats)}, "
            f"Watchouts={len(watchouts)}, "
            f"Status={output.validation_results.overall_status}"
        )

        return output

    # =========================================================
    # Helper: Convert LLM output to enriched SWOTItems
    # =========================================================
    def _enrich_items(self, llm_output, themes_by_category, benchmark_quality):
        """Convert LLM raw output into enriched SWOTItems with full scoring."""
        report = SWOTReport()
        is_low_benchmark = benchmark_quality in ("low", "unavailable")

        quadrant_map = {
            "strengths": llm_output.swot_report.strengths,
            "weaknesses": llm_output.swot_report.weaknesses,
            "opportunities": llm_output.swot_report.opportunities,
            "threats": llm_output.swot_report.threats,
        }

        for quadrant_name, llm_items in quadrant_map.items():
            enriched_list = []
            for llm_item in llm_items:
                # Look up theme data
                theme_data = self._lookup_theme(
                    llm_item.source_theme,
                    themes_by_category,
                )

                # Compute scoring
                freq = theme_data.frequency if theme_data else llm_item.frequency
                freq_norm = normalize_frequency(freq)

                perf = (
                    compute_sentiment_performance(theme_data.sentiment_balance)
                    if theme_data
                    else 5.0
                )

                priority = compute_strategic_priority(
                    importance=llm_item.scoring.importance,
                    impact=llm_item.scoring.impact,
                    confidence=llm_item.scoring.confidence,
                    freq_norm=freq_norm,
                )

                # Build enriched item
                item = SWOTItem(
                    item_id=f"{quadrant_name[0].upper()}_{slugify(llm_item.title)}",
                    quadrant=quadrant_name,
                    title=llm_item.title,
                    reasoning=llm_item.reasoning,
                    source_theme=llm_item.source_theme,
                    tags=llm_item.tags,
                    scoring=SWOTScoring(
                        importance=llm_item.scoring.importance,
                        impact=llm_item.scoring.impact,
                        confidence=llm_item.scoring.confidence,
                        frequency_norm=freq_norm,
                        performance_score=perf,
                        strategic_priority=priority,
                    ),
                    evidence_refs=llm_item.evidence_refs[:EVIDENCE_DISPLAY_CAP],
                    evidence_summary=EvidenceSummary(
                        source_mentions=freq,
                        source_frequency=freq,
                        available_evidence_refs=len(llm_item.evidence_refs),
                        displayed_evidence_refs=min(
                            EVIDENCE_DISPLAY_CAP, len(llm_item.evidence_refs)
                        ),
                        evidence_cap_applied=(
                            len(llm_item.evidence_refs) > EVIDENCE_DISPLAY_CAP
                        ),
                    ),
                    low_benchmark_quality=(
                        is_low_benchmark and quadrant_name in ("opportunities", "threats")
                    ),
                    claim_strength=(
                        ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
                        if (is_low_benchmark and quadrant_name in ("opportunities", "threats"))
                        else ClaimStrength.VALIDATED.value
                    ),
                )
                enriched_list.append(item)

            setattr(report, quadrant_name, enriched_list)

        return report

    def _lookup_theme(self, source_theme, themes_by_category):
        """Lookup a theme by source name in the themes_by_category map."""
        if source_theme in themes_by_category:
            entity_dict = themes_by_category[source_theme]
            for entity_type in ("target_business", "comparative", "competitor"):
                if entity_type in entity_dict:
                    return entity_dict[entity_type]
            for theme in entity_dict.values():
                return theme
        return None