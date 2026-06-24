"""
swot_agent_v7_0.py
==================

SWOT Analysis Agent v7.0 — Production-grade Business Intelligence Pipeline (Stage 4)

Pipeline position:
    Scraper → Preprocessing → Theme Extractor → [SWOT v7.0] → Strategy
                                                                  ↓
                                                          Brief Generator
                                                                  ↓
                                                Poster + Reels + Caption
                                                                  ↓
                                                            Dashboard

Version history:
    7.0 (2025-01) — Implements ALL 14 critical fixes:
        FIX 1  — Separate core SWOT from watchouts
        FIX 2  — Handle shadow weaknesses safely (route to watchouts by default)
        FIX 3  — Transparent evidence counts (source_mentions vs displayed)
        FIX 4  — Conservative benchmark quality (high/medium/low/unavailable)
        FIX 5  — Correct importance-performance matrix (sentiment-based)
        FIX 6  — Detect semantic overlaps & cross-quadrant conflicts
        FIX 7  — Complete low-benchmark tracking
        FIX 8  — Prevent unsupported strategic summary claims
        FIX 9  — Link derived opportunities to parent strengths
        FIX 10 — Clarify top summary fields (top_strength, top_watchout, etc.)
        FIX 11 — Downstream agent safety fields (should_feed_*)
        FIX 12 — Rewrite strategic summary safely (no absolute language when low)
        FIX 13 — Comprehensive quality report (11 sub-lists + consistency_violations)
        FIX 14 — Validation test function (8 standalone tests)

    6.x — Initial multi-provider scaffolding
    5.x — Theme-based ingestion overhaul
    <=4.x — Legacy review-list inputs (deprecated)

Author: SWOT Architecture Team
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 2. IMPORTS
# ---------------------------------------------------------------------------
import argparse
import json
import logging
import os
import re
import sys
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Tuple

# Third-party (optional imports guarded)
try:
    from pydantic import BaseModel, Field, ConfigDict, field_validator, AliasChoices
except ImportError as exc:  # pragma: no cover
    raise ImportError("Pydantic v2 is required. Install with: pip install pydantic>=2.0") from exc

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass  # optional

# Provider SDKs (all optional — guarded)
try:
    from google import genai as google_genai  # google-genai >= 0.3
    from google.genai import types as genai_types
    _HAS_VERTEX = True
except ImportError:
    google_genai = None  # type: ignore
    genai_types = None  # type: ignore
    _HAS_VERTEX = False

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    anthropic = None  # type: ignore
    _HAS_ANTHROPIC = False

try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    openai = None  # type: ignore
    _HAS_OPENAI = False

try:
    import groq
    _HAS_GROQ = True
except ImportError:
    groq = None  # type: ignore
    _HAS_GROQ = False


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("swot_agent_v7")


# ===========================================================================
# 3. CONSTANTS BLOCK — All thresholds configurable
# ===========================================================================
ENGINE_VERSION = "7.0"

# Theme ingest filters
MIN_THEME_FREQUENCY = 2
MIN_SENTIMENT_TOTAL = 2

# Sentiment ratios
POSITIVE_RATIO_STRENGTH = 0.70
NEGATIVE_RATIO_WEAKNESS = 0.35
SHADOW_MIN_NEGATIVE_MIX_RATIO = 0.15

# Shadow promotion rules (FIX 2)
SHADOW_PROMOTION_RULES = {
    "min_negative_ratio": 0.35,
    "min_negative_mentions": 3,
    "requires_manual_review": True,
}

# Benchmark thresholds (FIX 4)
BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR = 10
BENCHMARK_MEDIUM_MIN_COMPETITORS_AT_THRESHOLD = 2
RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR = 10

# Evidence cap (FIX 3)
EVIDENCE_DISPLAY_CAP = 10

# Performance score clamps (FIX 5)
WEAKNESS_MAX_PERFORMANCE = 4.5
STRENGTH_MIN_PERFORMANCE = 5.5
WEAKNESS_SCORING_ISSUE_FLOOR = 8.0
STRENGTH_SCORING_ISSUE_CEILING = 4.0

# Strategic priority weights (canonical)
PRIORITY_WEIGHT_IMPORTANCE = 0.35
PRIORITY_WEIGHT_IMPACT = 0.25
PRIORITY_WEIGHT_CONFIDENCE = 0.20
PRIORITY_WEIGHT_FREQUENCY = 0.20

# LLM Defaults
DEFAULT_VERTEX_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

# Retry behaviour
MAX_RETRIES_PER_PROVIDER = 3
RETRY_BACKOFF_BASE_SECONDS = 1.0  # 1, 2, 4

# Cost estimates (USD per call — rough heuristic)
COST_ESTIMATE_USD = {
    "vertex_ai": 0.012,
    "anthropic": 0.025,
    "openai": 0.020,
    "groq": 0.001,
    "rule_based": 0.0,
}

# Normalization
FREQUENCY_NORMALIZATION_CEILING = 25  # mentions >=25 → score 10


# ===========================================================================
# 4. ENUMS
# ===========================================================================
class LLMProvider(str, Enum):
    """LLM provider identifiers."""
    VERTEX_AI = "vertex_ai"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GROQ = "groq"
    RULE_BASED = "rule_based"
    AUTO = "auto"


class SWOTTag(str, Enum):
    """Item-level SWOT tags."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    COMPETITIVE = "competitive"
    OPERATIONAL = "operational"
    CUSTOMER_FACING = "customer_facing"


class ClaimStrength(str, Enum):
    """How strongly a claim is supported (FIX 11)."""
    VALIDATED = "validated"
    INTERNALLY_SUPPORTED = "internally_supported"
    DIRECTIONAL_NOT_VALIDATED = "directional_not_validated"
    EARLY_WARNING = "early_warning"


class Quadrant(str, Enum):
    STRENGTHS = "strengths"
    WEAKNESSES = "weaknesses"
    OPPORTUNITIES = "opportunities"
    THREATS = "threats"


# ===========================================================================
# 5. INPUT SCHEMAS
# ===========================================================================
class SentimentBalance(BaseModel):
    """Distribution of sentiments across mentions of a theme."""
    model_config = ConfigDict(extra="ignore")
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    mixed: int = 0

    @property
    def total(self) -> int:
        return self.positive + self.negative + self.neutral + self.mixed

    def ratio(self, key: str) -> float:
        t = self.total
        if t == 0:
            return 0.0
        return getattr(self, key, 0) / t


class ReviewTheme(BaseModel):
    """A theme block as emitted by the Theme Extractor (stage 3).

    NOTE: The Theme Extractor emits `frequency_count` and
    `sentiment_distribution`, not `frequency` / `sentiment_balance`. Both
    names are accepted via validation_alias so themes load correctly
    regardless of which key the upstream stage used. Without this, the
    mismatched keys were silently dropped (extra="ignore") and every theme
    fell back to frequency=0 / sentiment_balance=zeros, causing Stage 1 to
    reject 100% of themes.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    theme_name: Optional[str] = None
    theme_category: str
    entity_type: str = "target_business"  # target_business | competitor | comparative
    frequency: int = Field(
        default=0,
        validation_alias=AliasChoices("frequency", "frequency_count"),
    )
    sentiment_balance: SentimentBalance = Field(
        default_factory=SentimentBalance,
        validation_alias=AliasChoices("sentiment_balance", "sentiment_distribution"),
    )
    confidence_score: Optional[float] = None
    comparative_signal: Optional[str] = None
    target_score: Optional[float] = None
    competitor_score: Optional[float] = None
    performance_gap: Optional[float] = None
    mentions: List[str] = Field(default_factory=list)
    evidence_refs: List[Any] = Field(default_factory=list)
    representative_quotes: List[str] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    """Optional competitor metadata, used for benchmark quality assessment."""
    model_config = ConfigDict(extra="ignore")
    name: str
    review_count: int = 0


class ReviewsSummary(BaseModel):
    """Optional summary block from upstream stages."""
    model_config = ConfigDict(extra="ignore")
    target_review_count: int = 0
    competitor_review_counts: Dict[str, int] = Field(default_factory=dict)


class BusinessProfile(BaseModel):
    """The complete input ingested by the SWOT agent."""
    model_config = ConfigDict(extra="ignore")
    business_name: str
    business_type: Optional[str] = "unknown"
    themes: List[ReviewTheme] = Field(default_factory=list)
    positive_signals: List[Any] = Field(default_factory=list)
    opportunity_signals: List[Any] = Field(default_factory=list)
    threat_signals: List[Any] = Field(default_factory=list)
    negative_signals: List[Any] = Field(default_factory=list)
    comparison_summary: Dict[str, List[Any]] = Field(default_factory=dict)
    competitors: List[CompetitorProfile] = Field(default_factory=list)
    reviews_summary: Optional[ReviewsSummary] = None


# ===========================================================================
# 6. OUTPUT SCHEMAS
# ===========================================================================
class SWOTScoring(BaseModel):
    """Numeric scoring block for a SWOT item."""
    model_config = ConfigDict(extra="ignore")
    importance: float = 5.0          # 0-10
    impact: float = 5.0              # 0-10
    confidence: float = 0.5          # 0-1
    frequency_norm: float = 0.0      # 0-10 normalized
    performance_score: float = 5.0   # 0-10 (FIX 5)
    strategic_priority: float = 5.0  # 0-10 (canonical formula)


class EvidenceSummary(BaseModel):
    """Transparent evidence accounting (FIX 3)."""
    model_config = ConfigDict(extra="ignore")
    source_mentions: int = 0
    source_frequency: int = 0
    available_evidence_refs: int = 0
    displayed_evidence_refs: int = 0
    evidence_cap_applied: bool = False
    evidence_cap_limit: int = EVIDENCE_DISPLAY_CAP


class SWOTItem(BaseModel):
    """Confirmed SWOT item (strength / weakness / opportunity / threat)."""
    model_config = ConfigDict(extra="ignore")
    item_id: str
    quadrant: str  # strengths|weaknesses|opportunities|threats
    title: str
    reasoning: str
    source_theme: str
    tags: List[str] = Field(default_factory=list)
    scoring: SWOTScoring = Field(default_factory=SWOTScoring)
    evidence_refs: List[Any] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    pi_zone: Optional[str] = None
    vulnerability_score: Optional[float] = None
    is_shadow: bool = False
    low_benchmark_quality: bool = False
    # FIX 11 safety fields
    should_feed_strategy_agent: bool = True
    should_feed_campaign_planner: bool = True
    claim_strength: str = ClaimStrength.VALIDATED.value
    manual_review_only: bool = False
    parent_item_id: Optional[str] = None
    parent_theme: Optional[str] = None


class WatchoutItem(BaseModel):
    """A minor negative signal embedded inside an overall-positive theme (FIX 1/2)."""
    model_config = ConfigDict(extra="ignore")
    watchout_id: str
    title: str
    parent_item_id: Optional[str] = None
    parent_theme: str
    reasoning: str
    severity: str = "low"  # low|medium|high
    scope: str = "internal"
    manual_review_only: bool = True
    evidence_refs: List[Any] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    recommended_action: str = ""
    claim_strength: str = ClaimStrength.EARLY_WARNING.value
    is_shadow: bool = True
    should_feed_strategy_agent: bool = False
    should_feed_campaign_planner: bool = False
    low_benchmark_quality: bool = False


class DerivedOpportunity(BaseModel):
    """Opportunity derived from a parent Strength (FIX 9)."""
    model_config = ConfigDict(extra="ignore")
    item_id: str
    title: str
    reasoning: str
    opportunity_type: str = "strength_extension"
    derived_from: List[str] = Field(default_factory=list)
    parent_theme: str
    source_theme: str
    claim_strength: str = ClaimStrength.INTERNALLY_SUPPORTED.value
    recommended_strategy_type: str = "SO"
    evidence_refs: List[Any] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    scoring: SWOTScoring = Field(default_factory=SWOTScoring)
    should_feed_strategy_agent: bool = True
    should_feed_campaign_planner: bool = True
    manual_review_only: bool = False
    low_benchmark_quality: bool = False


class DirectionalCompetitiveSignal(BaseModel):
    """Low-confidence competitor signal (FIX 4)."""
    model_config = ConfigDict(extra="ignore")
    signal_id: str
    title: str
    reasoning: str
    direction: str = "advantage"   # advantage|disadvantage|parity
    source_theme: str
    benchmark_quality: str = "low"
    competitor_review_counts: Dict[str, int] = Field(default_factory=dict)
    claim_strength: str = ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
    should_feed_strategy_agent: bool = True
    should_feed_campaign_planner: bool = False
    manual_review_only: bool = True
    evidence_refs: List[Any] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    low_benchmark_quality: bool = True


class QualityReportItem(BaseModel):
    """Generic quality report row."""
    model_config = ConfigDict(extra="allow")
    item_id: Optional[str] = None
    issue: str = ""
    severity: Optional[str] = None
    theme: Optional[str] = None
    description: Optional[str] = None
    recommended_resolution: Optional[str] = None
    type: Optional[str] = None


class QualityReport(BaseModel):
    """All 11 sub-lists (FIX 13)."""
    model_config = ConfigDict(extra="ignore")
    unsupported_items: List[QualityReportItem] = Field(default_factory=list)
    duplicate_items: List[QualityReportItem] = Field(default_factory=list)
    semantic_overlaps: List[QualityReportItem] = Field(default_factory=list)
    cross_quadrant_theme_conflicts: List[QualityReportItem] = Field(default_factory=list)
    scoring_issues: List[QualityReportItem] = Field(default_factory=list)
    benchmark_warnings: List[QualityReportItem] = Field(default_factory=list)
    summary_issues: List[QualityReportItem] = Field(default_factory=list)
    low_confidence_items: List[QualityReportItem] = Field(default_factory=list)
    generic_items: List[QualityReportItem] = Field(default_factory=list)
    manual_review_needed: List[QualityReportItem] = Field(default_factory=list)
    consistency_violations: List[QualityReportItem] = Field(default_factory=list)


class SWOTReport(BaseModel):
    """Core SWOT quadrants — CONFIRMED items only (no shadows in weaknesses)."""
    model_config = ConfigDict(extra="ignore")
    strengths: List[SWOTItem] = Field(default_factory=list)
    weaknesses: List[SWOTItem] = Field(default_factory=list)
    opportunities: List[SWOTItem] = Field(default_factory=list)
    threats: List[SWOTItem] = Field(default_factory=list)


class StrategicContext(BaseModel):
    """Strategic envelope (FIX 4/7)."""
    model_config = ConfigDict(extra="ignore")
    quadrant_counts: Dict[str, int] = Field(default_factory=dict)
    benchmark_quality: str = "unavailable"
    benchmark_summary: Dict[str, Any] = Field(default_factory=dict)
    low_benchmark_items: List[str] = Field(default_factory=list)
    watchout_items: List[str] = Field(default_factory=list)
    shadow_weakness_items: List[str] = Field(default_factory=list)


class StrategicSummary(BaseModel):
    """Top-level summary with disambiguated top_* fields (FIX 10/12)."""
    model_config = ConfigDict(extra="ignore")
    main_advantage: str = ""
    most_critical_risk: str = ""
    best_growth_opportunity: str = ""
    top_strength: str = ""
    top_confirmed_weakness: str = ""
    top_watchout: str = ""
    top_opportunity: str = ""
    top_derived_opportunity: str = ""
    top_confirmed_threat: str = ""
    top_directional_threat: str = ""


class PriorityInsight(BaseModel):
    model_config = ConfigDict(extra="ignore")
    insight: str
    related_items: List[str] = Field(default_factory=list)
    priority: int = 5


class AmbiguousFactor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    factor: str
    reasoning: str
    source_theme: str
    suggested_resolution: str = ""


class ValidationResults(BaseModel):
    """FIX 14 — Validation test results."""
    model_config = ConfigDict(extra="ignore")
    tests_passed: int = 0
    tests_failed: int = 0
    violations: List[str] = Field(default_factory=list)
    overall_status: str = "PASS"


class EngineMeta(BaseModel):
    """Run metadata."""
    model_config = ConfigDict(extra="ignore")
    engine_version: str = ENGINE_VERSION
    llm_provider_used: str = "rule_based"
    llm_model_used: str = "n/a"
    fallback_used: bool = True
    total_themes: int = 0
    filtered_themes: int = 0
    low_confidence_count: int = 0
    processing_time_ms: int = 0
    dry_run: bool = False
    cost_estimate_usd: float = 0.0


class SWOTOutput(BaseModel):
    """Final SWOT report — top-level object."""
    model_config = ConfigDict(extra="ignore")
    business_type: str = "unknown"
    engine_version: str = ENGINE_VERSION
    swot_report: SWOTReport = Field(default_factory=SWOTReport)
    watchouts: List[WatchoutItem] = Field(default_factory=list)
    derived_opportunities: List[DerivedOpportunity] = Field(default_factory=list)
    directional_competitive_signals: List[DirectionalCompetitiveSignal] = Field(default_factory=list)
    strategic_summary: StrategicSummary = Field(default_factory=StrategicSummary)
    priority_insights: List[PriorityInsight] = Field(default_factory=list)
    ambiguous_factors: List[AmbiguousFactor] = Field(default_factory=list)
    matrix_outputs: Dict[str, List[Any]] = Field(default_factory=lambda: {
        "importance_performance_matrix": [],
        "opportunity_threat_matrix": [],
        "vulnerability_matrix": [],
    })
    strategic_context: StrategicContext = Field(default_factory=StrategicContext)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    validation_results: ValidationResults = Field(default_factory=ValidationResults)
    meta: EngineMeta = Field(default_factory=EngineMeta)


# ===========================================================================
# 7. LLM SCHEMAS — smaller semantic-core (LLM produces only these)
# ===========================================================================
class LLMScoring(BaseModel):
    model_config = ConfigDict(extra="ignore")
    importance: float = 5.0
    impact: float = 5.0
    confidence: float = 0.5


class LLMSWOTItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    reasoning: str
    source_theme: str
    quadrant: str
    tags: List[str] = Field(default_factory=list)
    scoring: LLMScoring = Field(default_factory=LLMScoring)
    evidence_refs: List[Any] = Field(default_factory=list)
    frequency: int = 0


class LLMSWOTReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    strengths: List[LLMSWOTItem] = Field(default_factory=list)
    weaknesses: List[LLMSWOTItem] = Field(default_factory=list)
    opportunities: List[LLMSWOTItem] = Field(default_factory=list)
    threats: List[LLMSWOTItem] = Field(default_factory=list)


class LLMStrategicSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    main_advantage: str = ""
    most_critical_risk: str = ""
    best_growth_opportunity: str = ""


class LLMSWOTOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    swot_report: LLMSWOTReport = Field(default_factory=LLMSWOTReport)
    strategic_summary: LLMStrategicSummary = Field(default_factory=LLMStrategicSummary)


# ===========================================================================
# 8. THEME VALIDATION FUNCTIONS
# ===========================================================================
def validate_review_themes(themes: List[ReviewTheme]) -> Tuple[List[ReviewTheme], int]:
    """Filter themes that do not meet minimum evidence requirements.

    Rejects themes where frequency < MIN_THEME_FREQUENCY AND sentiment_total < MIN_SENTIMENT_TOTAL.

    Returns:
        (kept_themes, rejected_count)
    Edge cases:
        - Empty themes list returns ([], 0).
        - Themes with frequency=1 are removed (e.g., 'cleanliness' in Volume Cafe).
    """
    if not themes:
        return [], 0
    kept: List[ReviewTheme] = []
    rejected = 0
    for t in themes:
        sentiment_total = t.sentiment_balance.total
        if t.frequency < MIN_THEME_FREQUENCY and sentiment_total < MIN_SENTIMENT_TOTAL:
            rejected += 1
            logger.debug("Rejecting theme '%s' (freq=%d, sentiment_total=%d)",
                         t.theme_category, t.frequency, sentiment_total)
            continue
        kept.append(t)
    return kept, rejected


def merge_themes_by_category(themes: List[ReviewTheme]) -> Dict[str, Dict[str, ReviewTheme]]:
    """Group themes by theme_category, indexed by entity_type.

    Returns:
        { theme_category: { entity_type: ReviewTheme } }
    """
    grouped: Dict[str, Dict[str, ReviewTheme]] = {}
    for t in themes:
        grouped.setdefault(t.theme_category, {})[t.entity_type] = t
    return grouped


# ---------------------------------------------------------------------------
# Semantic Theme Aliasing (NEW)
# ---------------------------------------------------------------------------

THEME_ALIAS_MAP: Dict[str, str] = {
    # service family
    "staff_behavior": "service",
    "service_speed": "service",
    "customer_experience": "service",

    # atmosphere family
    "cleanliness": "ambience",
    "crowding": "ambience",

    # food family
    "coffee_quality": "food_quality",
    "menu_variety": "food_quality",

    # value family
    "value_perception": "pricing",
}


def normalize_and_merge_similar_themes(
    themes: List[ReviewTheme],
) -> List[ReviewTheme]:
    """
    Merge semantically similar themes BEFORE the LLM stage.

    Example:
        'staff_behavior' + 'service_speed' -> 'service'
        'cleanliness' + 'crowding'         -> 'ambience'

    Merging strategy:
        - Group by (canonical_category, entity_type)
        - Sum frequencies
        - Sum sentiment distribution
        - Deduplicate mentions
        - Cap evidence references

    NOTE: the first theme encountered for each (canonical, entity_type) key
    is deep-copied before being used as the merge target. `themes` may be
    the same ReviewTheme objects still referenced by the caller's original
    BusinessProfile.themes list (validate_review_themes() filters by
    reference, it doesn't copy) — mutating them in place would silently
    rewrite theme_category/frequency/sentiment on the caller's original
    objects too. Copying avoids that aliasing bug.
    """
    merged: Dict[Tuple[str, str], ReviewTheme] = {}

    for t in themes:
        canonical = THEME_ALIAS_MAP.get(t.theme_category, t.theme_category)
        key = (canonical, t.entity_type)

        if key not in merged:
            merged_theme = t.model_copy(deep=True)
            merged_theme.theme_category = canonical
            merged[key] = merged_theme
        else:
            existing = merged[key]
            existing.frequency += t.frequency

            sb_old = existing.sentiment_balance
            sb_new = t.sentiment_balance
            sb_old.positive += sb_new.positive
            sb_old.negative += sb_new.negative
            sb_old.neutral  += sb_new.neutral
            sb_old.mixed    += sb_new.mixed

            existing.mentions = list(set(existing.mentions + t.mentions))
            existing.evidence_refs = (
                existing.evidence_refs + t.evidence_refs
            )[:EVIDENCE_DISPLAY_CAP]

    logger.info(
        "[Pre-LLM] Semantic merge: %d themes -> %d after aliasing",
        len(themes), len(merged),
    )
    return list(merged.values())


def compute_theme_confidence(theme: ReviewTheme) -> float:
    """Compute a confidence score in [0,1] based on theme frequency and sentiment_total.

    Edge cases:
        - frequency=0 returns 0.0.
        - High frequency saturates around 1.0.
    """
    freq = max(theme.frequency, theme.sentiment_balance.total)
    if freq <= 0:
        return 0.0
    # Saturate at 20 mentions = 1.0
    return min(1.0, freq / 20.0)


def apply_comparison_confidence(
    target: Optional[ReviewTheme],
    competitor: Optional[ReviewTheme],
    competitor_review_counts: Dict[str, int],
) -> Tuple[Optional[float], str]:
    """Compute a comparison confidence and the recommended claim_strength.

    Returns:
        (confidence, claim_strength)
    """
    if not target or not competitor:
        return None, ClaimStrength.INTERNALLY_SUPPORTED.value
    min_reviews = min(competitor_review_counts.values()) if competitor_review_counts else 0
    if min_reviews >= BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR:
        return 0.9, ClaimStrength.VALIDATED.value
    if min_reviews >= 5:
        return 0.6, ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
    return 0.3, ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value


def assess_benchmark_quality(competitor_review_counts: Dict[str, int]) -> Tuple[str, Dict[str, Any]]:
    """Conservative benchmark quality assessment (FIX 4).

    Returns:
        (quality, summary_dict)
    """
    if not competitor_review_counts:
        return "unavailable", {
            "competitor_review_counts": {},
            "minimum_reviews_seen": 0,
            "recommended_minimum_reviews_per_competitor": RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR,
            "recommendation": "No competitor data available; comparative claims cannot be validated.",
        }
    counts = competitor_review_counts
    values = list(counts.values())
    min_seen = min(values)
    qualifying = sum(1 for v in values if v >= BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR)

    if all(v >= BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR for v in values):
        quality = "high"
        rec = "Benchmark sufficient: every competitor meets the minimum review threshold."
    elif qualifying >= BENCHMARK_MEDIUM_MIN_COMPETITORS_AT_THRESHOLD:
        quality = "medium"
        rec = "Benchmark partially sufficient; some competitors are under-sampled."
    else:
        quality = "low"
        rec = (f"Benchmark thin: each competitor has fewer than "
               f"{BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR} reviews. "
               f"Treat all comparative claims as directional only.")

    summary = {
        "competitor_review_counts": counts,
        "minimum_reviews_seen": min_seen,
        "recommended_minimum_reviews_per_competitor": RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR,
        "recommendation": rec,
    }
    return quality, summary


# ===========================================================================
# Utility helpers
# ===========================================================================
def slugify(text: str) -> str:
    """Slugify a string for use in item_ids."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_").lower()
    return s or "item"


def normalize_frequency(freq: int) -> float:
    """Normalize a frequency count to a 0-10 scale."""
    if freq <= 0:
        return 0.0
    return min(10.0, (freq / FREQUENCY_NORMALIZATION_CEILING) * 10.0)


def compute_sentiment_performance(sb: SentimentBalance) -> float:
    """FIX 5 — sentiment-based performance score on a 0-10 scale."""
    t = sb.total
    if t == 0:
        return 5.0
    pos_r = sb.positive / t
    neg_r = sb.negative / t
    neu_r = sb.neutral / t
    mix_r = sb.mixed / t
    return (pos_r * 10.0) + (mix_r * 5.0) + (neu_r * 5.0) + (neg_r * 0.0)


def compute_strategic_priority(
    importance: float, impact: float, confidence: float, freq_norm: float
) -> float:
    """Canonical strategic priority formula."""
    return (
        importance * PRIORITY_WEIGHT_IMPORTANCE
        + impact * PRIORITY_WEIGHT_IMPACT
        + (confidence * 10.0) * PRIORITY_WEIGHT_CONFIDENCE
        + freq_norm * PRIORITY_WEIGHT_FREQUENCY
    )


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ===========================================================================
# 9. RULE-BASED FALLBACK GENERATOR
# ===========================================================================
def generate_rule_based_swot(profile: BusinessProfile,
                             benchmark_quality: str) -> LLMSWOTOutput:
    """Deterministic SWOT generator — used as fallback if all LLM providers fail.

    Pure Python, no external calls. Produces an LLMSWOTOutput shaped object
    that downstream enrichment can consume.

    Rules:
        - overperforms + pos_ratio >= POSITIVE_RATIO_STRENGTH → Strength
        - neg_ratio >= NEGATIVE_RATIO_WEAKNESS AND freq >= 3 → Weakness
        - target absent + competitor strong → Threat
        - competitor underperforms + gap → Opportunity
    """
    grouped = merge_themes_by_category(profile.themes)
    strengths: List[LLMSWOTItem] = []
    weaknesses: List[LLMSWOTItem] = []
    opportunities: List[LLMSWOTItem] = []
    threats: List[LLMSWOTItem] = []

    for theme_cat, by_entity in grouped.items():
        target = by_entity.get("target_business")
        competitor = by_entity.get("competitor")
        if target:
            sb = target.sentiment_balance
            pos_r = sb.ratio("positive")
            neg_r = sb.ratio("negative")
            freq = target.frequency

            if pos_r >= POSITIVE_RATIO_STRENGTH and freq >= 2:
                strengths.append(LLMSWOTItem(
                    title=f"Strong {theme_cat.replace('_', ' ')}",
                    reasoning=f"Customer reviews consistently praise {theme_cat.replace('_', ' ')} "
                              f"({sb.positive}/{sb.total} positive mentions).",
                    source_theme=theme_cat,
                    quadrant="strengths",
                    tags=["internal", "positive"],
                    scoring=LLMScoring(importance=7.5, impact=7.0, confidence=min(1.0, freq / 15.0)),
                    evidence_refs=target.mentions[:EVIDENCE_DISPLAY_CAP],
                    frequency=freq,
                ))
            if neg_r >= NEGATIVE_RATIO_WEAKNESS and freq >= 3:
                weaknesses.append(LLMSWOTItem(
                    title=f"Concerns around {theme_cat.replace('_', ' ')}",
                    reasoning=f"Repeated negative mentions of {theme_cat.replace('_', ' ')} "
                              f"({sb.negative}/{sb.total}).",
                    source_theme=theme_cat,
                    quadrant="weaknesses",
                    tags=["internal", "negative"],
                    scoring=LLMScoring(importance=6.5, impact=6.5, confidence=min(1.0, freq / 15.0)),
                    evidence_refs=target.mentions[:EVIDENCE_DISPLAY_CAP],
                    frequency=freq,
                ))

        if competitor and not target:
            sb = competitor.sentiment_balance
            if sb.ratio("positive") >= POSITIVE_RATIO_STRENGTH:
                threats.append(LLMSWOTItem(
                    title=f"Competitor strong in {theme_cat.replace('_', ' ')}",
                    reasoning=f"Competitors receive positive mentions on {theme_cat} "
                              f"({sb.positive}/{sb.total}) while target has no presence.",
                    source_theme=theme_cat,
                    quadrant="threats",
                    tags=["external", "competitive"],
                    scoring=LLMScoring(importance=6.0, impact=6.0, confidence=0.4),
                    evidence_refs=competitor.mentions[:EVIDENCE_DISPLAY_CAP],
                    frequency=competitor.frequency,
                ))

        if competitor and target:
            comp_neg = competitor.sentiment_balance.ratio("negative")
            tgt_pos = target.sentiment_balance.ratio("positive")
            if comp_neg >= 0.30 and tgt_pos >= 0.50:
                opportunities.append(LLMSWOTItem(
                    title=f"Capitalize on weak competitor {theme_cat.replace('_', ' ')}",
                    reasoning=f"Competitors underperform on {theme_cat}; "
                              f"target has positive sentiment and could capture switchers.",
                    source_theme=theme_cat,
                    quadrant="opportunities",
                    tags=["external", "competitive"],
                    scoring=LLMScoring(importance=6.0, impact=6.5, confidence=0.5),
                    evidence_refs=(target.mentions + competitor.mentions)[:EVIDENCE_DISPLAY_CAP],
                    frequency=max(target.frequency, competitor.frequency),
                ))

    return LLMSWOTOutput(
        swot_report=LLMSWOTReport(
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
        ),
        strategic_summary=LLMStrategicSummary(
            main_advantage=(strengths[0].title if strengths else "No clear advantage identified."),
            most_critical_risk=(weaknesses[0].title if weaknesses else (threats[0].title if threats else "No critical risk identified.")),
            best_growth_opportunity=(opportunities[0].title if opportunities else "No clear opportunity identified."),
        ),
    )


# ===========================================================================
# 10. PROMPT BUILDERS
# ===========================================================================
SYSTEM_PROMPT = dedent("""
    You are SWOT-AGENT-v7, a precise business intelligence analyst.

    Your job: convert structured customer-review theme data into a clean SWOT
    report. You are part of a larger automated pipeline; downstream agents will
    consume your output verbatim, so accuracy and conservatism matter.

    HARD CONSTRAINTS:
      • Output STRICT JSON matching the LLMSWOTOutput schema (no prose, no markdown).
      • Schema:
          {
            "swot_report": {
              "strengths":     [LLMSWOTItem],
              "weaknesses":    [LLMSWOTItem],
              "opportunities": [LLMSWOTItem],
              "threats":       [LLMSWOTItem]
            },
            "strategic_summary": {
              "main_advantage": "...",
              "most_critical_risk": "...",
              "best_growth_opportunity": "..."
            }
          }
      • Each LLMSWOTItem:
          {
            "title": "...",
            "reasoning": "...",
            "source_theme": "<theme_category>",
            "quadrant": "strengths|weaknesses|opportunities|threats",
            "tags": ["..."],
            "scoring": {"importance": 0-10, "impact": 0-10, "confidence": 0-1},
            "evidence_refs": [...],
            "frequency": int
          }

    ═══════════════════════════════════════════
    STRICT THEME CONSOLIDATION RULES
    ═══════════════════════════════════════════
      • Merge semantically similar themes into a SINGLE insight.
        Examples:
          - service + staff_behavior + service_speed  -> ONE service insight
          - ambience + cleanliness + crowding          -> ONE atmosphere insight
          - coffee_quality + menu_variety               -> ONE food/menu insight
      • NEVER produce two SWOT items that describe the same underlying concept.
      • Prefer ONE strong consolidated item over multiple redundant ones.

    ═══════════════════════════════════════════
    NO DUPLICATION ACROSS QUADRANTS
    ═══════════════════════════════════════════
      • A single concept must appear in ONLY ONE quadrant (S / W / O / T).
      • If a theme has BOTH positive and negative signals:
          - Place it in the dominant quadrant (>=70% sentiment direction).
          - Mention the minor signal inside `reasoning`, NOT as a separate item.
      • Do not duplicate the same idea in Strengths AND Opportunities.

    REASONING RULES:
      1. NEVER fabricate weaknesses if no negative signals exist. An empty
         negative_signals array means the business has no confirmed weaknesses.
      2. If a theme is overall positive (positive_ratio >= 0.70) but has a
         minor negative sub-signal, KEEP it as a Strength — do NOT add it as
         a Weakness. (Post-processor will create a Watchout.)
      3. If benchmark_quality is "low" or "medium", DO NOT use absolute
         language like "significantly exceeds competitors". Prefer:
            "shows a directional advantage in available data"
            "requires more competitor reviews before confirmation"
      4. Strategic_summary may ONLY reference concepts that appear as items
         in your SWOT report. Do not introduce new themes in the summary.
      5. Each item must cite a source_theme that exists in the provided themes.
      6. You produce ONLY the semantic core: title, reasoning, scoring, tags,
         source_theme, frequency, evidence_refs. You do NOT compute item_ids,
         strategic_priority, pi_zone, vulnerability_score, or shadow flags —
         the post-processor handles those.

    ═══════════════════════════════════════════
    CLASSIFICATION DISCIPLINE
    ═══════════════════════════════════════════
      • Strengths     = INTERNAL clear positives (>=70% positive sentiment).
      • Weaknesses    = INTERNAL clear negatives (>=35% negative sentiment).
      • Opportunities = EXTERNAL growth, competitor gaps, or strength extensions.
      • Threats       = EXTERNAL competitor advantages or market risks.

    ═══════════════════════════════════════════
    QUALITY RULES
    ═══════════════════════════════════════════
      • Prefer FEWER high-quality items over many redundant ones.
      • Each item must reference distinct evidence (source_theme + frequency).
      • No generic statements without supporting context.
      • Use evidence-based reasoning ONLY.

    Be conservative. Be evidence-driven. Output JSON only.
""").strip()


def build_user_prompt(profile: BusinessProfile,
                      kept_themes: List[ReviewTheme],
                      benchmark_quality: str,
                      benchmark_summary: Dict[str, Any]) -> str:
    """Construct the user prompt with theme context."""
    themes_payload = []
    for t in kept_themes:
        themes_payload.append({
            "theme_category": t.theme_category,
            "entity_type": t.entity_type,
            "frequency": t.frequency,
            "sentiment_balance": t.sentiment_balance.model_dump(),
            "target_score": t.target_score,
            "competitor_score": t.competitor_score,
            "performance_gap": t.performance_gap,
            "mention_count": len(t.mentions),
            "evidence_refs_sample": t.evidence_refs[:5],
        })

    payload = {
        "business_name": profile.business_name,
        "business_type": profile.business_type,
        "themes": themes_payload,
        "positive_signals": profile.positive_signals,
        "opportunity_signals": profile.opportunity_signals,
        "threat_signals": profile.threat_signals,
        "negative_signals": profile.negative_signals,
        "comparison_summary": profile.comparison_summary,
        "benchmark_quality": benchmark_quality,
        "benchmark_summary": benchmark_summary,
    }

    extra_rules = dedent("""
        ═══════════════════════════════════════════
        CRITICAL INSTRUCTIONS FOR THIS RUN
        ═══════════════════════════════════════════
        1. Themes have already been pre-merged. Treat each theme as ATOMIC.
        2. Do NOT split one theme into multiple SWOT items.
        3. If two themes describe the same concept, MERGE them into one item.
        4. Avoid placing related concepts in both Strengths and Opportunities.
        5. If you cannot find clear negative signals, leave Weaknesses EMPTY.
           Do NOT invent weaknesses just to fill the quadrant.
        6. Maximum recommended items per quadrant: 5
           (prioritize by strategic value, not quantity).
    """).strip()

    user_prompt = dedent(f"""
        Analyze the following business and produce a SWOT report as JSON.

        BENCHMARK QUALITY: {benchmark_quality}
        (If "low" or "medium", use cautious, directional language for comparisons.)

        {extra_rules}

        BUSINESS DATA:
        {json.dumps(payload, indent=2, default=str)}

        Return JSON only. No prose, no markdown fences.
    """).strip()

    return user_prompt


# ===========================================================================
# 11. LLM CLIENT ABSTRACTION + PROVIDERS
# ===========================================================================
class LLMClientError(Exception):
    """Raised when an LLM call fails."""


class LLMClient(ABC):
    """Abstract base class for LLM providers."""

    provider_name: str = "base"
    model_name: str = "unknown"

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send a system+user prompt and return the raw response text (JSON)."""
        raise NotImplementedError

    def complete_with_retries(self, system: str, user: str,
                              max_retries: int = MAX_RETRIES_PER_PROVIDER) -> str:
        """Retry wrapper with exponential backoff."""
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return self.complete(system, user)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                msg = str(e).lower()
                # Distinguish non-retryable
                if any(code in msg for code in ["401", "unauthorized", "invalid_api_key", "400"]):
                    logger.warning("[%s] Non-retryable error: %s", self.provider_name, e)
                    raise LLMClientError(f"{self.provider_name} non-retryable: {e}") from e
                backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("[%s] Attempt %d/%d failed: %s — retrying in %.1fs",
                               self.provider_name, attempt + 1, max_retries, e, backoff)
                time.sleep(backoff)
        raise LLMClientError(f"{self.provider_name} failed after {max_retries} attempts: {last_exc}")


class VertexAIGeminiClient(LLMClient):
    """Vertex AI Gemini provider (google-genai SDK in vertexai mode)."""
    provider_name = "vertex_ai"

    def __init__(self, model: str = DEFAULT_VERTEX_MODEL):
        if not _HAS_VERTEX:
            raise LLMClientError("google-genai not installed.")
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise LLMClientError("GOOGLE_CLOUD_PROJECT env not set.")
        self.model_name = model
        self.client = google_genai.Client(vertexai=True, project=project, location=location)

    def complete(self, system: str, user: str) -> str:
        cfg = genai_types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            system_instruction=system,
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
            if hasattr(genai_types, "ThinkingConfig") else None,
        )
        resp = self.client.models.generate_content(
            model=self.model_name,
            contents=user,
            config=cfg,
        )
        return resp.text or "{}"


class AnthropicClaudeClient(LLMClient):
    """Anthropic Claude provider (direct SDK)."""
    provider_name = "anthropic"

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL):
        if not _HAS_ANTHROPIC:
            raise LLMClientError("anthropic not installed.")
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMClientError("ANTHROPIC_API_KEY env not set.")
        self.model_name = model
        self.client = anthropic.Anthropic(api_key=key)

    def complete(self, system: str, user: str) -> str:
        forced = system + "\n\nIMPORTANT: Respond with ONLY a single valid JSON object. No prose."
        msg = self.client.messages.create(
            model=self.model_name,
            max_tokens=8000,
            temperature=0.0,
            system=forced,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks
        text_blocks = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "".join(text_blocks) or "{}"


class OpenAIGPTClient(LLMClient):
    """OpenAI GPT provider."""
    provider_name = "openai"

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL):
        if not _HAS_OPENAI:
            raise LLMClientError("openai not installed.")
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMClientError("OPENAI_API_KEY env not set.")
        self.model_name = model
        self.client = openai.OpenAI(api_key=key)

    def complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "{}"


class GroqClient(LLMClient):
    """Groq (free-tier safety net) provider."""
    provider_name = "groq"

    def __init__(self, model: str = DEFAULT_GROQ_MODEL):
        if not _HAS_GROQ:
            raise LLMClientError("groq not installed.")
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMClientError("GROQ_API_KEY env not set.")
        self.model_name = model
        self.client = groq.Groq(api_key=key)

    def complete(self, system: str, user: str) -> str:
        forced = system + "\n\nReturn JSON only."
        resp = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": forced},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "{}"


class LLMClientFactory:
    """Builds the provider fallback chain."""

    PROVIDER_ORDER = [
        LLMProvider.VERTEX_AI,
        LLMProvider.ANTHROPIC,
        LLMProvider.OPENAI,
        LLMProvider.GROQ,
    ]

    @classmethod
    def build_chain(cls, preferred: LLMProvider = LLMProvider.AUTO,
                    model_override: Optional[str] = None) -> List[LLMClient]:
        """Construct an ordered list of LLMClient instances to try."""
        chain: List[LLMClient] = []
        order = cls.PROVIDER_ORDER if preferred == LLMProvider.AUTO else (
            [preferred] + [p for p in cls.PROVIDER_ORDER if p != preferred]
        )
        for p in order:
            try:
                if p == LLMProvider.VERTEX_AI:
                    chain.append(VertexAIGeminiClient(
                        model=model_override if (preferred == LLMProvider.VERTEX_AI and model_override) else DEFAULT_VERTEX_MODEL
                    ))
                elif p == LLMProvider.ANTHROPIC:
                    chain.append(AnthropicClaudeClient(
                        model=model_override if (preferred == LLMProvider.ANTHROPIC and model_override) else DEFAULT_ANTHROPIC_MODEL
                    ))
                elif p == LLMProvider.OPENAI:
                    chain.append(OpenAIGPTClient(
                        model=model_override if (preferred == LLMProvider.OPENAI and model_override) else DEFAULT_OPENAI_MODEL
                    ))
                elif p == LLMProvider.GROQ:
                    chain.append(GroqClient(
                        model=model_override if (preferred == LLMProvider.GROQ and model_override) else DEFAULT_GROQ_MODEL
                    ))
            except LLMClientError as e:
                logger.info("Skipping provider %s: %s", p.value, e)
        return chain


def call_llm_chain(chain: List[LLMClient], system: str, user: str) -> Tuple[Optional[str], Optional[LLMClient]]:
    """Try each client in order until one succeeds.

    Returns:
        (response_text, successful_client) or (None, None) if all failed.
    """
    for client in chain:
        try:
            logger.info("Attempting LLM provider: %s (%s)", client.provider_name, client.model_name)
            text = client.complete_with_retries(system, user)
            logger.info("LLM provider %s succeeded.", client.provider_name)
            return text, client
        except Exception as e:  # noqa: BLE001
            logger.warning("Provider %s failed: %s", client.provider_name, e)
            continue
    return None, None


def safe_parse_json(text: str) -> Dict[str, Any]:
    """Parse JSON safely, attempting to strip markdown fences if present."""
    if not text:
        return {}
    raw = text.strip()
    # Strip ```json fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find first { ... } block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("Failed to parse LLM JSON; returning empty dict.")
    return {}


# ===========================================================================
# 14. THEME FILE ADAPTER
# ===========================================================================
class ThemeFileAdapter:
    """Parses theme.json files into BusinessProfile objects."""

    @staticmethod
    def load(path: Path) -> BusinessProfile:
        """Load and validate a theme.json file."""
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return ThemeFileAdapter.from_dict(data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> BusinessProfile:
        """Build a BusinessProfile from a dict."""
        # Try to extract competitor review counts if present in reviews_summary
        comp_counts = {}
        rs = data.get("reviews_summary") or {}
        if isinstance(rs, dict):
            comp_counts = rs.get("competitor_review_counts", {}) or {}

        # Also synthesize counts from competitors[] if provided
        competitors_raw = data.get("competitors", []) or []
        competitor_objs = []
        for c in competitors_raw:
            if isinstance(c, dict):
                name = c.get("name", "competitor")
                rc = c.get("review_count", 0)
                competitor_objs.append(CompetitorProfile(name=name, review_count=rc))
                comp_counts.setdefault(name, rc)

        profile = BusinessProfile(
            business_name=data.get("business_name", "Unknown Business"),
            business_type=data.get("business_type", "unknown"),
            themes=[ReviewTheme.model_validate(t) for t in data.get("themes", [])],
            positive_signals=data.get("positive_signals", []),
            opportunity_signals=data.get("opportunity_signals", []),
            threat_signals=data.get("threat_signals", []),
            negative_signals=data.get("negative_signals", []),
            comparison_summary=data.get("comparison_summary", {}),
            competitors=competitor_objs,
            reviews_summary=ReviewsSummary(
                target_review_count=rs.get("target_review_count", 0),
                competitor_review_counts=comp_counts,
            ) if rs or competitor_objs else None,
        )
        return profile


# ===========================================================================
# 13. SWOT POST PROCESSOR
# ===========================================================================
class SWOTPostProcessor:
    """Implements all post-LLM enrichment stages (4-10)."""

    def __init__(self, profile: BusinessProfile,
                 kept_themes: List[ReviewTheme],
                 benchmark_quality: str,
                 benchmark_summary: Dict[str, Any]):
        self.profile = profile
        self.kept_themes = kept_themes
        self.benchmark_quality = benchmark_quality
        self.benchmark_summary = benchmark_summary
        # quick lookups
        self.theme_index = merge_themes_by_category(kept_themes)
        self._id_counter: Dict[str, int] = {}

    # -- STAGE 4: ENRICH ITEMS -----------------------------------------------
    def _next_id(self, quadrant_letter: str, theme: str) -> str:
        """Generate item_id in format {Q}_{theme_slug}_{nn}."""
        key = f"{quadrant_letter}_{slugify(theme)}"
        self._id_counter[key] = self._id_counter.get(key, 0) + 1
        return f"{key}_{self._id_counter[key]:02d}"

    def _get_target_theme(self, theme_category: str) -> Optional[ReviewTheme]:
        return self.theme_index.get(theme_category, {}).get("target_business")

    def _build_evidence_summary(self, theme: Optional[ReviewTheme],
                                evidence_refs: List[Any]) -> Tuple[EvidenceSummary, List[Any]]:
        """FIX 3 — Build transparent evidence summary; cap displayed refs."""
        source_freq = theme.frequency if theme else 0
        available = len(theme.evidence_refs) if theme else len(evidence_refs)
        capped = evidence_refs[:EVIDENCE_DISPLAY_CAP]
        summary = EvidenceSummary(
            source_mentions=source_freq,
            source_frequency=source_freq,
            available_evidence_refs=available,
            displayed_evidence_refs=len(capped),
            evidence_cap_applied=available > EVIDENCE_DISPLAY_CAP,
            evidence_cap_limit=EVIDENCE_DISPLAY_CAP,
        )
        return summary, capped

    def _compute_scoring(self, theme: Optional[ReviewTheme],
                         llm_scoring: LLMScoring,
                         quadrant: str) -> SWOTScoring:
        """FIX 5 — Sentiment-based performance + canonical priority."""
        sb = theme.sentiment_balance if theme else SentimentBalance()
        freq = theme.frequency if theme else 0
        sentiment_perf = compute_sentiment_performance(sb)
        freq_norm = normalize_frequency(freq)

        if self.benchmark_quality == "high" and theme and theme.performance_gap is not None:
            comparative = clamp(5.0 + theme.performance_gap * 5.0, 0.0, 10.0)
            performance = (sentiment_perf * 0.6) + (comparative * 0.4)
        else:
            performance = sentiment_perf

        # Quadrant-aware clamps
        if quadrant in ("weaknesses", "threats"):
            performance = min(performance, WEAKNESS_MAX_PERFORMANCE)
        elif quadrant == "strengths":
            performance = max(performance, STRENGTH_MIN_PERFORMANCE)

        # Confidence with traceability penalty
        confidence = llm_scoring.confidence
        if freq < 3:
            confidence *= 0.7
        if self.benchmark_quality in ("low", "unavailable") and quadrant in ("threats", "opportunities"):
            confidence *= 0.8
        confidence = clamp(confidence, 0.0, 1.0)

        priority = compute_strategic_priority(
            llm_scoring.importance, llm_scoring.impact, confidence, freq_norm
        )
        return SWOTScoring(
            importance=clamp(llm_scoring.importance, 0.0, 10.0),
            impact=clamp(llm_scoring.impact, 0.0, 10.0),
            confidence=confidence,
            frequency_norm=freq_norm,
            performance_score=round(performance, 2),
            strategic_priority=round(priority, 2),
        )

    def _enrich_item(self, llm_item: LLMSWOTItem, quadrant: str) -> SWOTItem:
        """Promote an LLMSWOTItem to a full SWOTItem with all v7.0 fields."""
        q_letter = {
            "strengths": "S", "weaknesses": "W",
            "opportunities": "O", "threats": "T",
        }.get(quadrant, "X")
        theme = self._get_target_theme(llm_item.source_theme)
        ev_summary, capped_refs = self._build_evidence_summary(theme, llm_item.evidence_refs)
        scoring = self._compute_scoring(theme, llm_item.scoring, quadrant)
        # PI zone
        importance = scoring.importance
        performance = scoring.performance_score
        if importance >= 6 and performance >= 6:
            pi_zone = "keep_up_good_work"
        elif importance >= 6 and performance < 6:
            pi_zone = "concentrate_here"
        elif importance < 6 and performance >= 6:
            pi_zone = "possible_overkill"
        else:
            pi_zone = "low_priority"

        # Vulnerability score (simple heuristic)
        vuln = None
        if quadrant in ("weaknesses", "threats"):
            vuln = round(min(10.0, (10.0 - performance) * 0.6 + importance * 0.4), 2)

        low_bench = self.benchmark_quality in ("low", "unavailable") and (
            "comp" in " ".join(llm_item.tags).lower() or quadrant in ("opportunities", "threats")
        )

        item = SWOTItem(
            item_id=self._next_id(q_letter, llm_item.source_theme),
            quadrant=quadrant,
            title=llm_item.title.strip(),
            reasoning=llm_item.reasoning.strip(),
            source_theme=llm_item.source_theme,
            tags=llm_item.tags,
            scoring=scoring,
            evidence_refs=capped_refs,
            evidence_summary=ev_summary,
            pi_zone=pi_zone,
            vulnerability_score=vuln,
            is_shadow=False,
            low_benchmark_quality=low_bench,
            claim_strength=ClaimStrength.VALIDATED.value,
        )
        # FIX 11 — default routing flags (refined in stage 7)
        item = self._apply_safety_fields(item)
        return item

    # -- STAGE 5: SHADOW ROUTER ---------------------------------------------
    def shadow_route(self, items_by_quadrant: Dict[str, List[SWOTItem]]
                     ) -> Tuple[Dict[str, List[SWOTItem]], List[WatchoutItem]]:
        """FIX 1 & 2 — Detect shadow weaknesses inside otherwise-positive strengths.

        For each strength whose underlying theme has >=15% negative/mixed mentions:
            - If positive_ratio >= 0.70 → Watchout (manual_review_only=True)
            - Else if negative_ratio >= 0.35 and neg_mentions >= 3 → confirm as Weakness
            - Else → Watchout
        """
        watchouts: List[WatchoutItem] = []
        new_items = {k: list(v) for k, v in items_by_quadrant.items()}

        for strength in list(items_by_quadrant.get("strengths", [])):
            theme = self._get_target_theme(strength.source_theme)
            if not theme:
                continue
            sb = theme.sentiment_balance
            t = sb.total
            if t == 0:
                continue
            neg_mix_ratio = (sb.negative + sb.mixed) / t
            if neg_mix_ratio < SHADOW_MIN_NEGATIVE_MIX_RATIO:
                continue

            pos_ratio = sb.positive / t
            neg_ratio = sb.negative / t

            if pos_ratio >= POSITIVE_RATIO_STRENGTH:
                # Route to Watchout — keep strength intact
                w = self._build_watchout_from_strength(strength, theme,
                                                      reason="minor_negative_subsignal")
                watchouts.append(w)
            elif (neg_ratio >= SHADOW_PROMOTION_RULES["min_negative_ratio"]
                  and sb.negative >= SHADOW_PROMOTION_RULES["min_negative_mentions"]
                  and self.benchmark_quality != "unavailable"):
                # Promote to confirmed weakness
                confirmed = self._build_confirmed_weakness_from_theme(strength, theme)
                new_items.setdefault("weaknesses", []).append(confirmed)
                # Remove strength
                new_items["strengths"] = [s for s in new_items["strengths"]
                                          if s.item_id != strength.item_id]
            else:
                # Watchout
                w = self._build_watchout_from_strength(strength, theme,
                                                      reason="insufficient_negative_evidence")
                watchouts.append(w)
        return new_items, watchouts

    def _build_watchout_from_strength(self, parent: SWOTItem,
                                      theme: ReviewTheme,
                                      reason: str) -> WatchoutItem:
        sb = theme.sentiment_balance
        ev_summary, capped_refs = self._build_evidence_summary(
            theme, theme.evidence_refs or theme.mentions
        )
        wid = self._next_id("WO", theme.theme_category)
        title = f"Minor concern within {theme.theme_category.replace('_', ' ')}"
        reasoning = (
            f"Theme '{theme.theme_category}' is overall positive "
            f"(positive_ratio={sb.ratio('positive'):.2f}) but contains "
            f"{sb.negative} negative and {sb.mixed} mixed mentions. "
            f"Flagging as a watchout for manual review (reason: {reason})."
        )
        severity = "medium" if (sb.negative + sb.mixed) / max(sb.total, 1) >= 0.25 else "low"
        wo = WatchoutItem(
            watchout_id=wid,
            title=title,
            parent_item_id=parent.item_id,
            parent_theme=theme.theme_category,
            reasoning=reasoning,
            severity=severity,
            scope="internal",
            manual_review_only=True,
            evidence_refs=capped_refs,
            evidence_summary=ev_summary,
            recommended_action="Investigate the negative sub-signal manually before acting.",
            claim_strength=ClaimStrength.EARLY_WARNING.value,
            is_shadow=True,
            should_feed_strategy_agent=False,
            should_feed_campaign_planner=False,
        )
        return wo

    def _build_confirmed_weakness_from_theme(self, parent: SWOTItem,
                                             theme: ReviewTheme) -> SWOTItem:
        sb = theme.sentiment_balance
        ev_summary, capped_refs = self._build_evidence_summary(
            theme, theme.evidence_refs or theme.mentions
        )
        wid = self._next_id("W", theme.theme_category)
        title = f"Confirmed issue within {theme.theme_category.replace('_', ' ')}"
        reasoning = (
            f"Theme '{theme.theme_category}' shows significant negative volume "
            f"({sb.negative}/{sb.total} negative). Promoted from a watchout to a "
            f"confirmed weakness."
        )
        scoring = self._compute_scoring(theme, LLMScoring(importance=6.5, impact=6.5, confidence=0.7),
                                        "weaknesses")
        return SWOTItem(
            item_id=wid,
            quadrant="weaknesses",
            title=title,
            reasoning=reasoning,
            source_theme=theme.theme_category,
            tags=["internal", "negative"],
            scoring=scoring,
            evidence_refs=capped_refs,
            evidence_summary=ev_summary,
            pi_zone="concentrate_here",
            vulnerability_score=round(10.0 - scoring.performance_score, 2),
            is_shadow=False,
            parent_item_id=parent.item_id,
            parent_theme=theme.theme_category,
            claim_strength=ClaimStrength.VALIDATED.value,
            should_feed_strategy_agent=True,
            should_feed_campaign_planner=False,
        )

    # -- CROSS-QUADRANT DEDUPLICATION (Post-LLM, NEW) ------------------------
    def deduplicate_across_quadrants(
        self,
        items_by_quadrant: Dict[str, List[SWOTItem]],
    ) -> Dict[str, List[SWOTItem]]:
        """
        Prevents the same concept from appearing in multiple SWOT quadrants.
        Keeps the version with the highest strategic_priority.

        NOTE: operates on items_by_quadrant (Dict[str, List[SWOTItem]]) rather
        than a SWOTReport instance — at this point in the pipeline (between
        Stage 5 shadow routing and Stage 6 derivation) no SWOTReport object
        exists yet; it's only assembled at the very end of analyze(). This
        also means dedup runs before derive_opportunities/build_directional_signals,
        so they see deduplicated, not redundant, strengths.

        Items with no source_theme are kept as-is rather than dropped: keying
        every untagged item on the same empty string would either collapse
        unrelated untagged items into one another or (with a bare `continue`)
        silently delete them from the report. Each gets a unique fallback key
        instead so it survives dedup untouched.
        """
        all_items: List[Tuple[str, SWOTItem]] = [
            (q_name, item)
            for q_name, items in items_by_quadrant.items()
            for item in items
        ]

        seen: Dict[str, Tuple[str, SWOTItem]] = {}
        for q_name, item in all_items:
            key = (item.source_theme or "").lower().strip()
            if not key:
                key = f"_unkeyed_{id(item)}"

            if key not in seen:
                seen[key] = (q_name, item)
            else:
                _, existing_item = seen[key]
                if item.scoring.strategic_priority > existing_item.scoring.strategic_priority:
                    seen[key] = (q_name, item)

        deduped: Dict[str, List[SWOTItem]] = {
            "strengths": [], "weaknesses": [], "opportunities": [], "threats": [],
        }
        for q_name, item in seen.values():
            deduped[q_name].append(item)

        logger.info(
            "[Post-LLM] Cross-quadrant dedup: %d items -> %d unique concepts",
            len(all_items), len(seen),
        )
        return deduped

    # -- STAGE 6: DERIVED OPPORTUNITIES + DIRECTIONAL SIGNALS ----------------
    def derive_opportunities(self, items_by_quadrant: Dict[str, List[SWOTItem]]
                             ) -> List[DerivedOpportunity]:
        """FIX 9 — Link same-theme S→O pairs as derived opportunities."""
        strengths = items_by_quadrant.get("strengths", [])
        opportunities = items_by_quadrant.get("opportunities", [])
        strength_themes = {s.source_theme: s for s in strengths}

        derived: List[DerivedOpportunity] = []
        for opp in opportunities:
            parent = strength_themes.get(opp.source_theme)
            if not parent:
                continue
            theme = self._get_target_theme(opp.source_theme)
            ev_summary, capped_refs = self._build_evidence_summary(
                theme, opp.evidence_refs
            )
            did = self._next_id("DO", opp.source_theme)
            d = DerivedOpportunity(
                item_id=did,
                title=f"Extend strength: {parent.title}",
                reasoning=(f"Opportunity '{opp.title}' shares the theme '{opp.source_theme}' "
                           f"with confirmed strength '{parent.title}'. Treat as an "
                           f"internally-derived growth angle (SO strategy)."),
                opportunity_type="strength_extension",
                derived_from=[parent.item_id],
                parent_theme=opp.source_theme,
                source_theme=opp.source_theme,
                claim_strength=ClaimStrength.INTERNALLY_SUPPORTED.value,
                recommended_strategy_type="SO",
                evidence_refs=capped_refs,
                evidence_summary=ev_summary,
                scoring=opp.scoring,
                should_feed_strategy_agent=True,
                should_feed_campaign_planner=True,
                manual_review_only=False,
                low_benchmark_quality=opp.low_benchmark_quality,
            )
            derived.append(d)
        return derived

    def build_directional_signals(self, items_by_quadrant: Dict[str, List[SWOTItem]]
                                  ) -> List[DirectionalCompetitiveSignal]:
        """FIX 4 — Thin-benchmark comparative items become directional signals."""
        signals: List[DirectionalCompetitiveSignal] = []
        if self.benchmark_quality == "high":
            return signals

        comp_counts = self.benchmark_summary.get("competitor_review_counts", {})
        for q in ("opportunities", "threats"):
            for item in items_by_quadrant.get(q, []):
                if not item.low_benchmark_quality:
                    continue
                sid = self._next_id("DS", item.source_theme)
                signals.append(DirectionalCompetitiveSignal(
                    signal_id=sid,
                    title=item.title,
                    reasoning=(f"Comparative signal derived from {item.source_theme}; "
                               f"benchmark is {self.benchmark_quality} so this is "
                               f"directional only and requires more competitor data."),
                    direction="advantage" if q == "opportunities" else "disadvantage",
                    source_theme=item.source_theme,
                    benchmark_quality=self.benchmark_quality,
                    competitor_review_counts=comp_counts,
                    claim_strength=ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value,
                    evidence_refs=item.evidence_refs,
                    evidence_summary=item.evidence_summary,
                    should_feed_strategy_agent=True,
                    should_feed_campaign_planner=False,
                    manual_review_only=True,
                    low_benchmark_quality=True,
                ))
        return signals

    # -- STAGE 7: SAFETY FIELDS ---------------------------------------------
    def _apply_safety_fields(self, item: SWOTItem) -> SWOTItem:
        """FIX 11 — set should_feed_* and claim_strength routing rules."""
        q = item.quadrant
        if q == "strengths":
            item.should_feed_strategy_agent = True
            item.should_feed_campaign_planner = True
            item.claim_strength = ClaimStrength.VALIDATED.value
            item.manual_review_only = False
        elif q == "weaknesses":
            item.should_feed_strategy_agent = True
            item.should_feed_campaign_planner = False
            item.claim_strength = ClaimStrength.VALIDATED.value
            item.manual_review_only = False
        elif q == "opportunities":
            item.should_feed_strategy_agent = True
            item.should_feed_campaign_planner = not item.low_benchmark_quality
            item.claim_strength = (ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
                                   if item.low_benchmark_quality
                                   else ClaimStrength.VALIDATED.value)
            item.manual_review_only = item.low_benchmark_quality
        elif q == "threats":
            item.should_feed_strategy_agent = True
            item.should_feed_campaign_planner = False
            item.claim_strength = (ClaimStrength.DIRECTIONAL_NOT_VALIDATED.value
                                   if item.low_benchmark_quality
                                   else ClaimStrength.VALIDATED.value)
            item.manual_review_only = item.low_benchmark_quality
        return item

    # -- STAGE 8: QUALITY CHECKS --------------------------------------------
    def run_quality_checks(self,
                           items_by_quadrant: Dict[str, List[SWOTItem]],
                           watchouts: List[WatchoutItem],
                           derived: List[DerivedOpportunity],
                           signals: List[DirectionalCompetitiveSignal]
                           ) -> QualityReport:
        """FIX 6/7/13 — Build the full 11-section quality report."""
        report = QualityReport()

        # 1. Generic items — title too short / vague
        for q, items in items_by_quadrant.items():
            for it in items:
                if len(it.title.split()) < 2 or "various" in it.title.lower():
                    report.generic_items.append(QualityReportItem(
                        item_id=it.item_id, issue="Title too generic",
                        theme=it.source_theme,
                    ))

        # 2. Duplicates — same title across quadrants
        seen_titles: Dict[str, str] = {}
        for q, items in items_by_quadrant.items():
            for it in items:
                key = it.title.strip().lower()
                if key in seen_titles:
                    report.duplicate_items.append(QualityReportItem(
                        item_id=it.item_id,
                        issue=f"Duplicate title shared with {seen_titles[key]}",
                        theme=it.source_theme,
                    ))
                else:
                    seen_titles[key] = it.item_id

        # 3. Semantic overlaps + cross-quadrant conflicts (FIX 6)
        themes_to_quadrants: Dict[str, List[Tuple[str, SWOTItem]]] = {}
        for q, items in items_by_quadrant.items():
            for it in items:
                themes_to_quadrants.setdefault(it.source_theme, []).append((q, it))

        for theme, occurrences in themes_to_quadrants.items():
            if len(occurrences) <= 1:
                continue
            quads = sorted({q for q, _ in occurrences})
            report.semantic_overlaps.append(QualityReportItem(
                theme=theme,
                issue=f"Theme '{theme}' appears in multiple quadrants: {quads}",
                type="semantic_overlap",
                severity="medium",
                description=f"Same theme used across {quads}",
            ))
            # Cross-quadrant conflict checks
            quad_set = set(quads)
            conflict = False
            details = ""
            if "strengths" in quad_set and "weaknesses" in quad_set:
                # Requires watchout / subtheme / ambiguity flag
                related_watchout = any(w.parent_theme == theme for w in watchouts)
                if not related_watchout:
                    conflict = True
                    details = "Strength + Weakness on same theme without watchout/ambiguity tag."
            if "weaknesses" in quad_set and "threats" in quad_set:
                # need internal/external separation
                tagsets = [set(it.tags) for q, it in occurrences if q in ("weaknesses", "threats")]
                if not (any("internal" in ts for ts in tagsets) and any("external" in ts for ts in tagsets)):
                    conflict = True
                    details = "Weakness + Threat on same theme without internal/external split."
            if "strengths" in quad_set and "opportunities" in quad_set:
                # Requires derived linkage
                has_derived = any(theme == d.parent_theme for d in derived)
                if not has_derived:
                    conflict = True
                    details = "Strength + Opportunity on same theme without derived_from linkage."
            if conflict:
                report.cross_quadrant_theme_conflicts.append(QualityReportItem(
                    theme=theme,
                    type="cross_quadrant_theme_conflict",
                    severity="high",
                    description=details,
                    recommended_resolution="Add subtheme distinction, watchout, or derived linkage.",
                ))

        # 4. Scoring issues (FIX 5)
        for it in items_by_quadrant.get("weaknesses", []):
            if it.scoring.performance_score >= WEAKNESS_SCORING_ISSUE_FLOOR:
                report.scoring_issues.append(QualityReportItem(
                    item_id=it.item_id,
                    issue=f"Weakness has high performance_score={it.scoring.performance_score}",
                    severity="high",
                    type="scoring_inconsistency",
                ))
        for it in items_by_quadrant.get("strengths", []):
            if it.scoring.performance_score <= STRENGTH_SCORING_ISSUE_CEILING:
                report.scoring_issues.append(QualityReportItem(
                    item_id=it.item_id,
                    issue=f"Strength has low performance_score={it.scoring.performance_score}",
                    severity="high",
                    type="scoring_inconsistency",
                ))

        # 5. Benchmark warnings (FIX 4/7)
        for q, items in items_by_quadrant.items():
            for it in items:
                if it.low_benchmark_quality:
                    report.benchmark_warnings.append(QualityReportItem(
                        item_id=it.item_id,
                        issue=("Item marked low_benchmark_quality but appears in a "
                               "primary quadrant; treat claim as directional."),
                        severity="medium",
                        theme=it.source_theme,
                        type="benchmark_quality_mismatch",
                    ))
        for d in derived:
            if d.low_benchmark_quality:
                report.benchmark_warnings.append(QualityReportItem(
                    item_id=d.item_id,
                    issue="Derived opportunity has low benchmark quality.",
                    severity="medium",
                ))
        for s in signals:
            if s.low_benchmark_quality:
                report.benchmark_warnings.append(QualityReportItem(
                    item_id=s.signal_id,
                    issue="Directional signal has low benchmark quality.",
                    severity="medium",
                ))

        # 6. Low confidence
        for q, items in items_by_quadrant.items():
            for it in items:
                if it.scoring.confidence < 0.4:
                    report.low_confidence_items.append(QualityReportItem(
                        item_id=it.item_id,
                        issue=f"Confidence={it.scoring.confidence:.2f} below 0.4",
                        severity="medium",
                    ))

        # 7. Manual review needed
        for w in watchouts:
            report.manual_review_needed.append(QualityReportItem(
                item_id=w.watchout_id,
                issue="Watchout requires manual review before promoting to weakness.",
                severity="medium",
            ))
        for s in signals:
            report.manual_review_needed.append(QualityReportItem(
                item_id=s.signal_id,
                issue="Directional competitive signal — manual review recommended.",
                severity="medium",
            ))

        # 11. Consistency violations — aggregate (FIX 13)
        aggregates: List[QualityReportItem] = []
        for ov in report.semantic_overlaps:
            aggregates.append(QualityReportItem(
                type="semantic_overlap", severity="medium",
                theme=ov.theme, description=ov.issue,
                recommended_resolution="Disambiguate or merge."
            ))
        for cv in report.cross_quadrant_theme_conflicts:
            aggregates.append(QualityReportItem(
                type=cv.type or "cross_quadrant_theme_conflict",
                severity=cv.severity or "high",
                theme=cv.theme, description=cv.description,
                recommended_resolution=cv.recommended_resolution,
            ))
        for si in report.scoring_issues:
            aggregates.append(QualityReportItem(
                type="scoring_inconsistency", severity=si.severity or "high",
                description=si.issue, recommended_resolution="Recompute or reclassify."
            ))
        for bw in report.benchmark_warnings:
            aggregates.append(QualityReportItem(
                type="benchmark_quality_mismatch", severity=bw.severity or "medium",
                description=bw.issue, recommended_resolution="Collect more competitor reviews."
            ))
        report.consistency_violations = aggregates
        return report

    # -- STAGE 9: SUMMARY + VALIDATION --------------------------------------
    def build_strategic_summary(self,
                                llm_summary: LLMStrategicSummary,
                                items_by_quadrant: Dict[str, List[SWOTItem]],
                                watchouts: List[WatchoutItem],
                                derived: List[DerivedOpportunity],
                                signals: List[DirectionalCompetitiveSignal],
                                quality_report: QualityReport
                                ) -> StrategicSummary:
        """FIX 8/10/12 — safe summary with all top_* fields and concept validation."""

        def best(items: List[SWOTItem]) -> Optional[SWOTItem]:
            return max(items, key=lambda x: x.scoring.strategic_priority, default=None)

        top_strength = best(items_by_quadrant.get("strengths", []))
        top_weakness = best(items_by_quadrant.get("weaknesses", []))
        top_opp = best(items_by_quadrant.get("opportunities", []))
        top_threat_all = items_by_quadrant.get("threats", [])
        confirmed_threats = [t for t in top_threat_all if not t.low_benchmark_quality]
        directional_threats = [t for t in top_threat_all if t.low_benchmark_quality]
        top_confirmed_threat = max(confirmed_threats, key=lambda x: x.scoring.strategic_priority, default=None)
        top_directional_threat = max(directional_threats, key=lambda x: x.scoring.strategic_priority, default=None)
        top_watchout = max(watchouts, key=lambda w: (w.severity == "high", w.severity == "medium"), default=None)
        top_derived = max(derived, key=lambda d: d.scoring.strategic_priority, default=None)

        # Build conservative narrative (FIX 12)
        def safe_phrase(item: Optional[SWOTItem], default: str = "") -> str:
            if not item:
                return default
            if item.low_benchmark_quality or self.benchmark_quality in ("low", "unavailable"):
                return f"{item.title} (directional only — benchmark is {self.benchmark_quality})"
            return item.title

        main_advantage = safe_phrase(top_strength, default="No clear advantage identified.")
        most_critical_risk = (
            top_weakness.title if top_weakness
            else (top_confirmed_threat.title if top_confirmed_threat
                  else (top_directional_threat.title + " (directional)" if top_directional_threat
                        else (top_watchout.title + " (watchout)" if top_watchout
                              else "No critical risk identified.")))
        )
        best_growth = (top_opp.title if top_opp
                       else (top_derived.title if top_derived
                             else "No clear growth opportunity identified."))

        # FIX 8 — concept validation: build supported vocabulary
        supported_tokens = set()
        for q, items in items_by_quadrant.items():
            for it in items:
                supported_tokens.update(_tokenize_concept(it.title))
                supported_tokens.update(_tokenize_concept(it.source_theme))
        for w in watchouts:
            supported_tokens.update(_tokenize_concept(w.title))
            supported_tokens.update(_tokenize_concept(w.parent_theme))
        for d in derived:
            supported_tokens.update(_tokenize_concept(d.title))
            supported_tokens.update(_tokenize_concept(d.source_theme))
        for s in signals:
            supported_tokens.update(_tokenize_concept(s.title))
            supported_tokens.update(_tokenize_concept(s.source_theme))
        for t in self.kept_themes:
            supported_tokens.update(_tokenize_concept(t.theme_category))

        def sanitize(text: str, field_name: str) -> str:
            if not text:
                return text
            tokens = _tokenize_concept(text)
            # Compute "content" tokens — words >3 chars and not stopwords
            content = [tok for tok in tokens if len(tok) > 3 and tok not in _STOP_TOKENS]
            unsupported = [tok for tok in content if tok not in supported_tokens]
            # Allow if all content tokens are supported, OR if most are.
            if unsupported and len(unsupported) >= max(1, len(content) // 2):
                quality_report.summary_issues.append(QualityReportItem(
                    issue=f"Unsupported concept(s) in {field_name}: {unsupported}",
                    severity="high",
                    description=f"Field='{field_name}', text='{text}'",
                    type="summary_unsupported",
                ))
                # Add to consistency violations
                quality_report.consistency_violations.append(QualityReportItem(
                    type="summary_unsupported", severity="high",
                    description=f"{field_name} references unsupported concepts: {unsupported}",
                    recommended_resolution="Remove unsupported concepts or back them with evidence.",
                ))
                # Replace with safe placeholder
                return "Insufficient evidence to summarize."
            return text

        main_advantage = sanitize(main_advantage, "main_advantage")
        most_critical_risk = sanitize(most_critical_risk, "most_critical_risk")
        best_growth = sanitize(best_growth, "best_growth_opportunity")

        return StrategicSummary(
            main_advantage=main_advantage,
            most_critical_risk=most_critical_risk,
            best_growth_opportunity=best_growth,
            top_strength=(top_strength.title if top_strength else ""),
            top_confirmed_weakness=(top_weakness.title if top_weakness else ""),
            top_watchout=(top_watchout.title if top_watchout else ""),
            top_opportunity=(top_opp.title if top_opp else ""),
            top_derived_opportunity=(top_derived.title if top_derived else ""),
            top_confirmed_threat=(top_confirmed_threat.title if top_confirmed_threat else ""),
            top_directional_threat=(top_directional_threat.title if top_directional_threat else ""),
        )

    # -- MATRICES ------------------------------------------------------------
    def build_matrices(self, items_by_quadrant: Dict[str, List[SWOTItem]]) -> Dict[str, List[Any]]:
        ipm = []
        for q in ("strengths", "weaknesses"):
            for it in items_by_quadrant.get(q, []):
                ipm.append({
                    "item_id": it.item_id,
                    "title": it.title,
                    "importance": it.scoring.importance,
                    "performance": it.scoring.performance_score,
                    "pi_zone": it.pi_zone,
                    "quadrant": q,
                })
        otm = []
        for q in ("opportunities", "threats"):
            for it in items_by_quadrant.get(q, []):
                otm.append({
                    "item_id": it.item_id,
                    "title": it.title,
                    "impact": it.scoring.impact,
                    "confidence": it.scoring.confidence,
                    "quadrant": q,
                })
        vuln = []
        for it in items_by_quadrant.get("weaknesses", []) + items_by_quadrant.get("threats", []):
            vuln.append({
                "item_id": it.item_id,
                "title": it.title,
                "vulnerability_score": it.vulnerability_score,
            })
        return {
            "importance_performance_matrix": ipm,
            "opportunity_threat_matrix": otm,
            "vulnerability_matrix": vuln,
        }


# ---------------------------------------------------------------------------
# Concept tokenization helpers (for FIX 8)
# ---------------------------------------------------------------------------
_STOP_TOKENS = {
    "the", "and", "with", "from", "this", "that", "have", "for", "into",
    "directional", "only", "benchmark", "available", "data", "more", "less",
    "based", "limited", "appears", "shows", "outperform", "competitor",
    "competitors", "review", "reviews", "early", "warning", "no", "clear",
    "critical", "risk", "growth", "opportunity", "advantage", "minor",
    "watchout", "confirmed", "concern", "concerns", "issue", "issues",
    "identified", "extend", "strength", "weakness", "threat", "directional)",
    "(directional", "insufficient", "evidence", "summarize", "to",
}


def _tokenize_concept(text: str) -> set:
    """Tokenize a string into normalized concept tokens for matching."""
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return set(tokens)


# ===========================================================================
# 15. VALIDATION TEST FUNCTION (FIX 14)
# ===========================================================================
def validate_swot_output(output: Dict[str, Any]) -> List[str]:
    """Run 8 standalone validation tests on a SWOTOutput dict.

    Returns:
        A list of violation strings. Empty list = all passed.
    """
    violations: List[str] = []

    swot_report = output.get("swot_report", {}) or {}
    weaknesses = swot_report.get("weaknesses", []) or []
    strengths = swot_report.get("strengths", []) or []
    opportunities = swot_report.get("opportunities", []) or []
    threats = swot_report.get("threats", []) or []
    watchouts = output.get("watchouts", []) or []
    derived = output.get("derived_opportunities", []) or []
    strategic_context = output.get("strategic_context", {}) or {}
    quality_report = output.get("quality_report", {}) or {}
    strategic_summary = output.get("strategic_summary", {}) or {}
    benchmark_summary = strategic_context.get("benchmark_summary", {}) or {}

    # TEST 1: Shadow items with positive_ratio >= 0.70 must NOT be in weaknesses
    for w in weaknesses:
        if w.get("is_shadow"):
            violations.append(
                f"TEST 1 FAIL: shadow item '{w.get('item_id')}' present in weaknesses."
            )

    # TEST 2: benchmark_quality != "high" if any competitor has < 10 reviews
    bq = strategic_context.get("benchmark_quality", "unavailable")
    counts = benchmark_summary.get("competitor_review_counts", {}) or {}
    if counts and bq == "high":
        if any(v < BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR for v in counts.values()):
            violations.append(
                "TEST 2 FAIL: benchmark_quality='high' but a competitor has <10 reviews."
            )

    # TEST 3: No weakness has performance_score >= 8
    for w in weaknesses:
        ps = (w.get("scoring") or {}).get("performance_score", 0)
        if ps >= WEAKNESS_SCORING_ISSUE_FLOOR:
            violations.append(
                f"TEST 3 FAIL: weakness '{w.get('item_id')}' has performance_score={ps}."
            )

    # TEST 4: All low_benchmark_quality items in strategic_context.low_benchmark_items
    low_bench_ids = set(strategic_context.get("low_benchmark_items", []) or [])
    all_items = strengths + weaknesses + opportunities + threats
    for it in all_items:
        if it.get("low_benchmark_quality") and it.get("item_id") not in low_bench_ids:
            violations.append(
                f"TEST 4 FAIL: low_benchmark item '{it.get('item_id')}' "
                f"missing from strategic_context.low_benchmark_items."
            )
    for d in derived:
        if d.get("low_benchmark_quality") and d.get("item_id") not in low_bench_ids:
            violations.append(
                f"TEST 4 FAIL: low_benchmark derived '{d.get('item_id')}' "
                f"missing from strategic_context.low_benchmark_items."
            )

    # TEST 5: All strategic_summary concepts have supporting evidence
    summary_issues = quality_report.get("summary_issues", []) or []
    flagged_unsupported = [i for i in summary_issues
                           if "unsupported" in (i.get("issue", "") + i.get("description", "") +
                                                i.get("type", "")).lower()]
    if flagged_unsupported:
        # If summary still contains the offending text, fail
        for issue in flagged_unsupported:
            desc = issue.get("description", "")
            if any(tok in json.dumps(strategic_summary).lower()
                   for tok in re.findall(r"[a-zA-Z]+", desc.lower())
                   if len(tok) > 4 and tok in ("cleanliness",)):
                violations.append(
                    f"TEST 5 FAIL: strategic_summary contains unsupported concept ({desc})."
                )

    # TEST 6: source_mentions and displayed_evidence_refs both shown when capped
    for it in all_items + watchouts + derived:
        ev = it.get("evidence_summary") or {}
        if ev.get("evidence_cap_applied"):
            if ev.get("source_mentions") is None or ev.get("displayed_evidence_refs") is None:
                violations.append(
                    f"TEST 6 FAIL: capped item '{it.get('item_id') or it.get('watchout_id')}' "
                    f"missing transparent evidence counts."
                )

    # TEST 7: Opportunity sharing theme with Strength has derived_from linkage
    strength_themes = {s.get("source_theme") for s in strengths}
    derived_themes = {d.get("parent_theme") for d in derived}
    for o in opportunities:
        if o.get("source_theme") in strength_themes:
            if o.get("source_theme") not in derived_themes:
                violations.append(
                    f"TEST 7 FAIL: opportunity '{o.get('item_id')}' shares theme "
                    f"with a Strength but has no derived_from linkage."
                )

    # TEST 8: consistency_violations not empty when issues exist elsewhere
    has_other_issues = any(
        quality_report.get(k) for k in (
            "unsupported_items", "duplicate_items", "semantic_overlaps",
            "cross_quadrant_theme_conflicts", "scoring_issues",
            "benchmark_warnings", "summary_issues",
        )
    )
    if has_other_issues and not quality_report.get("consistency_violations"):
        violations.append(
            "TEST 8 FAIL: consistency_violations empty but other quality sub-lists are populated."
        )

    return violations


# ===========================================================================
# 12. SWOT AGENT — Top-level orchestrator
# ===========================================================================
class SWOTAgent:
    """Top-level orchestrator: runs the 10-stage pipeline end to end."""

    def __init__(self,
                 provider: LLMProvider = LLMProvider.AUTO,
                 model: Optional[str] = None,
                 dry_run: bool = False):
        self.provider = provider
        self.model = model
        self.dry_run = dry_run

    def analyze(self, profile: BusinessProfile) -> SWOTOutput:
        """Run all 10 pipeline stages and return a SWOTOutput."""
        start = time.time()
        logger.info("=== SWOT v%s START — business: %s ===", ENGINE_VERSION, profile.business_name)

        # ----- STAGE 1: INGEST + VALIDATE THEMES -----
        s1 = time.time()
        kept_themes, rejected = validate_review_themes(profile.themes)
        logger.info("[Stage 1] Themes kept=%d rejected=%d in %.0fms",
                    len(kept_themes), rejected, (time.time() - s1) * 1000)

        # 🔥 NEW: merge semantically similar themes before LLM stage
        kept_themes = normalize_and_merge_similar_themes(kept_themes)

        # ----- Benchmark assessment -----
        comp_counts = {}
        if profile.reviews_summary:
            comp_counts = dict(profile.reviews_summary.competitor_review_counts)
        for c in profile.competitors:
            comp_counts.setdefault(c.name, c.review_count)
        benchmark_quality, benchmark_summary = assess_benchmark_quality(comp_counts)
        logger.info("Benchmark quality: %s (min_reviews=%d)",
                    benchmark_quality, benchmark_summary.get("minimum_reviews_seen", 0))

        # ----- STAGE 2: RULE-BASED CLASSIFIER (ground truth + fallback) -----
        s2 = time.time()
        rule_based_output = generate_rule_based_swot(
            BusinessProfile(**{**profile.model_dump(), "themes": kept_themes}),
            benchmark_quality,
        )
        logger.info("[Stage 2] Rule-based produced "
                    "S=%d W=%d O=%d T=%d in %.0fms",
                    len(rule_based_output.swot_report.strengths),
                    len(rule_based_output.swot_report.weaknesses),
                    len(rule_based_output.swot_report.opportunities),
                    len(rule_based_output.swot_report.threats),
                    (time.time() - s2) * 1000)

        # ----- STAGE 3: LLM SEMANTIC LAYER -----
        s3 = time.time()
        llm_output: LLMSWOTOutput = rule_based_output  # default
        provider_used = "rule_based"
        model_used = "n/a"
        fallback_used = True

        if not self.dry_run:
            chain = LLMClientFactory.build_chain(self.provider, self.model)
            if not chain:
                logger.warning("No LLM provider available; using rule-based output.")
            else:
                profile_for_llm = BusinessProfile(
                    **{**profile.model_dump(), "themes": kept_themes}
                )
                user_prompt = build_user_prompt(
                    profile_for_llm, kept_themes, benchmark_quality, benchmark_summary
                )
                raw_text, client = call_llm_chain(chain, SYSTEM_PROMPT, user_prompt)
                if raw_text and client:
                    parsed = safe_parse_json(raw_text)
                    try:
                        llm_output = LLMSWOTOutput.model_validate(parsed)
                        provider_used = client.provider_name
                        model_used = client.model_name
                        fallback_used = False
                    except Exception as e:  # noqa: BLE001
                        logger.warning("LLM output validation failed; using rule-based: %s", e)
        else:
            logger.info("[Stage 3] DRY RUN — skipping LLM call.")

        logger.info("[Stage 3] LLM stage finished in %.0fms (provider=%s)",
                    (time.time() - s3) * 1000, provider_used)

        # ----- STAGES 4-10: POST-PROCESSING -----
        pp = SWOTPostProcessor(profile, kept_themes, benchmark_quality, benchmark_summary)

        # Stage 4 — enrich each item from LLM into SWOTItem
        s4 = time.time()
        items_by_quadrant: Dict[str, List[SWOTItem]] = {
            "strengths": [], "weaknesses": [], "opportunities": [], "threats": [],
        }
        for q, items in [
            ("strengths", llm_output.swot_report.strengths),
            ("weaknesses", llm_output.swot_report.weaknesses),
            ("opportunities", llm_output.swot_report.opportunities),
            ("threats", llm_output.swot_report.threats),
        ]:
            for li in items:
                enriched = pp._enrich_item(li, q)
                items_by_quadrant[q].append(enriched)
        logger.info("[Stage 4] Enriched items in %.0fms", (time.time() - s4) * 1000)

        # Stage 5 — Shadow routing (FIX 1/2)
        s5 = time.time()
        items_by_quadrant, watchouts = pp.shadow_route(items_by_quadrant)
        logger.info("[Stage 5] Shadow routing produced %d watchouts in %.0fms",
                    len(watchouts), (time.time() - s5) * 1000)

        # 🔥 NEW: remove duplicate concepts across quadrants before deriving
        # opportunities/signals from them
        items_by_quadrant = pp.deduplicate_across_quadrants(items_by_quadrant)

        # Stage 6 — Derived opportunities + directional signals (FIX 9/4)
        s6 = time.time()
        derived = pp.derive_opportunities(items_by_quadrant)
        signals = pp.build_directional_signals(items_by_quadrant)
        logger.info("[Stage 6] Derived=%d Signals=%d in %.0fms",
                    len(derived), len(signals), (time.time() - s6) * 1000)

        # Stage 7 — safety fields applied during enrichment, refresh now
        for q, items in items_by_quadrant.items():
            for it in items:
                pp._apply_safety_fields(it)

        # Stage 8 — quality checks (FIX 6/7/13)
        s8 = time.time()
        quality_report = pp.run_quality_checks(items_by_quadrant, watchouts, derived, signals)
        logger.info("[Stage 8] Quality checks complete in %.0fms (consistency_violations=%d)",
                    (time.time() - s8) * 1000, len(quality_report.consistency_violations))

        # Stage 9 — strategic summary (FIX 8/10/12)
        s9 = time.time()
        strategic_summary = pp.build_strategic_summary(
            llm_output.strategic_summary, items_by_quadrant,
            watchouts, derived, signals, quality_report,
        )
        logger.info("[Stage 9] Strategic summary built in %.0fms", (time.time() - s9) * 1000)

        # Strategic context
        low_bench_ids: List[str] = []
        for q, items in items_by_quadrant.items():
            for it in items:
                if it.low_benchmark_quality:
                    low_bench_ids.append(it.item_id)
        for d in derived:
            if d.low_benchmark_quality:
                low_bench_ids.append(d.item_id)
        for s in signals:
            if s.low_benchmark_quality:
                low_bench_ids.append(s.signal_id)

        strategic_context = StrategicContext(
            quadrant_counts={q: len(v) for q, v in items_by_quadrant.items()},
            benchmark_quality=benchmark_quality,
            benchmark_summary=benchmark_summary,
            low_benchmark_items=low_bench_ids,
            watchout_items=[w.watchout_id for w in watchouts],
            shadow_weakness_items=[w.watchout_id for w in watchouts if w.is_shadow],
        )

        # Matrices
        matrices = pp.build_matrices(items_by_quadrant)

        # Build preliminary output for validation
        prelim_output = SWOTOutput(
            business_type=profile.business_type or "unknown",
            engine_version=ENGINE_VERSION,
            swot_report=SWOTReport(
                strengths=items_by_quadrant["strengths"],
                weaknesses=items_by_quadrant["weaknesses"],
                opportunities=items_by_quadrant["opportunities"],
                threats=items_by_quadrant["threats"],
            ),
            watchouts=watchouts,
            derived_opportunities=derived,
            directional_competitive_signals=signals,
            strategic_summary=strategic_summary,
            priority_insights=[],
            ambiguous_factors=[],
            matrix_outputs=matrices,
            strategic_context=strategic_context,
            quality_report=quality_report,
        )

        # Stage 10 — final validation (FIX 14)
        s10 = time.time()
        violations = validate_swot_output(prelim_output.model_dump())
        validation_results = ValidationResults(
            tests_passed=8 - len({v.split(" ")[0] for v in violations}),
            tests_failed=len({v.split(" ")[0] for v in violations}),
            violations=violations,
            overall_status=("PASS" if not violations else "FAIL"),
        )
        logger.info("[Stage 10] Validation %s (%d violations) in %.0fms",
                    validation_results.overall_status, len(violations),
                    (time.time() - s10) * 1000)

        # Low confidence count
        low_conf = sum(1 for q in items_by_quadrant.values()
                       for it in q if it.scoring.confidence < 0.4)
        elapsed_ms = int((time.time() - start) * 1000)
        meta = EngineMeta(
            engine_version=ENGINE_VERSION,
            llm_provider_used=provider_used,
            llm_model_used=model_used,
            fallback_used=fallback_used,
            total_themes=len(profile.themes),
            filtered_themes=rejected,
            low_confidence_count=low_conf,
            processing_time_ms=elapsed_ms,
            dry_run=self.dry_run,
            cost_estimate_usd=COST_ESTIMATE_USD.get(provider_used, 0.0),
        )

        prelim_output.validation_results = validation_results
        prelim_output.meta = meta

        logger.info("=== SWOT v%s COMPLETE in %dms — provider=%s status=%s ===",
                    ENGINE_VERSION, elapsed_ms, provider_used,
                    validation_results.overall_status)
        # Quality summary log line
        logger.info(
            "Quality summary: overlaps=%d cross_conflicts=%d scoring_issues=%d "
            "benchmark_warnings=%d summary_issues=%d watchouts=%d derived=%d signals=%d",
            len(quality_report.semantic_overlaps),
            len(quality_report.cross_quadrant_theme_conflicts),
            len(quality_report.scoring_issues),
            len(quality_report.benchmark_warnings),
            len(quality_report.summary_issues),
            len(watchouts),
            len(derived),
            len(signals),
        )
        return prelim_output


# ===========================================================================
# 16. CLI MAIN
# ===========================================================================
def main() -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="SWOT Analysis Agent v7.0 — Stage 4 of the BI pipeline.",
    )
    ap.add_argument("--input", required=True, type=Path, help="Path to input theme.json")
    ap.add_argument("--output", required=True, type=Path, help="Path to output swot_report.json")
    ap.add_argument("--provider", default="auto",
                    choices=[p.value for p in LLMProvider],
                    help="LLM provider preference (default: auto).")
    ap.add_argument("--model", default=None, help="Override default model for chosen provider.")
    ap.add_argument("--dry-run", action="store_true", help="Skip LLM calls; use rule-based only.")
    ap.add_argument("--verbose", action="store_true", help="Enable DEBUG logging.")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        profile = ThemeFileAdapter.load(args.input)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load input: %s", e)
        traceback.print_exc()
        return 2

    agent = SWOTAgent(
        provider=LLMProvider(args.provider),
        model=args.model,
        dry_run=args.dry_run,
    )

    try:
        output = agent.analyze(profile)
    except Exception as e:  # noqa: BLE001
        logger.error("SWOT analysis failed: %s", e)
        traceback.print_exc()
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output.model_dump(), f, indent=2, default=str)
    logger.info("Wrote SWOT report to %s", args.output)

    print(f"\n✓ SWOT v{ENGINE_VERSION} → {args.output}")
    print(f"  status: {output.validation_results.overall_status}")
    print(f"  provider: {output.meta.llm_provider_used} ({output.meta.llm_model_used})")
    print(f"  S/W/O/T: {len(output.swot_report.strengths)}/{len(output.swot_report.weaknesses)}"
          f"/{len(output.swot_report.opportunities)}/{len(output.swot_report.threats)}")
    print(f"  watchouts: {len(output.watchouts)}")
    print(f"  derived_opportunities: {len(output.derived_opportunities)}")
    print(f"  directional_signals: {len(output.directional_competitive_signals)}")
    print(f"  violations: {len(output.validation_results.violations)}")
    return 0 if output.validation_results.overall_status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

#     python swot_agent_v7_0.py --input theme.json --output swot_report.json \
#   --provider auto --model gemini-2.5-flash --dry-run --verbose