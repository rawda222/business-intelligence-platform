"""
strategy.py
===========

Strategy Agent v1.0 — Production-grade Strategic Synthesis (Pipeline Stage 5)

Pipeline position:
    Scraper → Preprocessing → Theme Extractor → SWOT v7.0 → [STRATEGY v1.0]
                                                                       ↓
                                                             Brief Generator
                                                                       ↓
                                                     Campaign Planner → Content/Creative/Compliance

Input:   SWOTOutput (swot_report.json) — full output of SWOT Agent v7.0
Output:  StrategyOutput (strategy_report.json) — consumed by Brief Generator

This module:
  • Filters SWOT inputs to honor `should_feed_strategy_agent` gating at the
    Python layer BEFORE the LLM sees any data.
  • Classifies a strategic posture via a 5-rule decision tree.
  • Builds a full TOWS cross-matrix (SO / ST / WO / WT).
  • Derives a ranked, time-horizoned Priority Action Plan.
  • Produces an effort-impact Resource Assessment grid.
  • Emits a Campaign Brief Feed scoped for the Campaign Planner.
  • Runs a Strategy Quality Report (5 checks) and enforces it post-hoc.

Author:  Strategy Architecture Team
Version: 1.0
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------
import json
import logging
import time
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError("Pydantic v2 is required.") from exc

# Reuse SWOT v7.0 primitives (LLMClient ABC, call_llm_chain, safe_parse_json,
# SWOTOutput schema). They live in the same project.
try:
    from swot_agent_v7_0 import (  # type: ignore
        SWOTOutput,
        LLMClient,
        call_llm_chain,
        safe_parse_json,
    )
except ImportError:  # pragma: no cover
    # Allow this file to be imported standalone for tests/inspection.
    SWOTOutput = Any  # type: ignore
    LLMClient = Any   # type: ignore

    def call_llm_chain(chain, system, user):  # type: ignore
        raise RuntimeError("swot_agent_v7_0 not available — cannot call LLM.")

    def safe_parse_json(text: str) -> Dict[str, Any]:  # type: ignore
        try:
            return json.loads(text)
        except Exception:
            return {}


logger = logging.getLogger("strategy_agent_v1")


# ===========================================================================
# CONSTANTS
# ===========================================================================
ENGINE_VERSION = "1.0"

# Max strategies per TOWS cell
MAX_SO_STRATEGIES = 3
MAX_ST_STRATEGIES = 2
MAX_WO_STRATEGIES = 2
MAX_WT_STRATEGIES = 2

MAX_PRIORITY_ACTIONS = 8
MAX_CAMPAIGN_FEED_ITEMS = 5

# Confidence weights for the urgency ranking formula
CONFIDENCE_WEIGHTS = {
    "confirmed": 1.0,
    "probable": 0.8,
    "exploratory": 0.5,
    "watchout_only": 0.2,
}
EFFORT_WEIGHTS = {"low": 1, "medium": 2, "high": 3}
IMPACT_WEIGHTS = {"low": 1, "medium": 2, "high": 3}

# Vulnerability threshold that forces immediate horizon for ST strategies
VULNERABILITY_IMMEDIATE_THRESHOLD = 6.0

# Strategic-priority threshold that flips LEVERAGE_LED posture on
LEVERAGE_PRIORITY_FLOOR = 8.0


# ===========================================================================
# ENUM-LIKE STRING CLASSES (per spec — kept as str subclasses for JSON cleanliness)
# ===========================================================================
class StrategyConfidence(str):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    EXPLORATORY = "exploratory"
    WATCHOUT = "watchout_only"


class StrategyHorizon(str):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class StrategyType(str):
    SO = "SO"
    ST = "ST"
    WO = "WO"
    WT = "WT"


class StrategicPosture(str):
    LEVERAGE_LED = "leverage_led"
    DEFENSE_LED = "defense_led"
    IMPROVEMENT_LED = "improvement_led"
    CONTINGENCY_LED = "contingency_led"
    BALANCED = "balanced"
    BLOCKED = "BLOCKED"


# Mapping from SWOT claim_strength → Strategy confidence
CLAIM_STRENGTH_TO_CONFIDENCE = {
    "validated": StrategyConfidence.CONFIRMED,
    "internally_supported": StrategyConfidence.PROBABLE,
    "directional_not_validated": StrategyConfidence.EXPLORATORY,
    "early_warning": StrategyConfidence.WATCHOUT,
}

CONFIDENCE_RANK = {
    StrategyConfidence.CONFIRMED: 4,
    StrategyConfidence.PROBABLE: 3,
    StrategyConfidence.EXPLORATORY: 2,
    StrategyConfidence.WATCHOUT: 1,
}


# ===========================================================================
# OUTPUT SCHEMA (Pydantic v2)
# ===========================================================================
class StrategyAnchor(BaseModel):
    """A SWOT item that anchors a strategy."""
    model_config = ConfigDict(extra="ignore")
    item_id: str
    title: str
    quadrant: str
    confidence: str
    strategic_priority: float = 0.0


class TOWSStrategy(BaseModel):
    """A single strategy generated from one TOWS cell."""
    model_config = ConfigDict(extra="ignore")
    strategy_id: str
    strategy_type: str
    title: str
    description: str
    rationale: str
    anchors: List[StrategyAnchor] = Field(default_factory=list)
    confidence: str
    horizon: str
    estimated_effort: str
    estimated_impact: str
    priority_rank: int
    tags: List[str] = Field(default_factory=list)
    requires_manual_review: bool = False
    downstream_campaign_eligible: bool = False
    watchout_flag: Optional[str] = None


class TOWSMatrix(BaseModel):
    """Complete 4-cell TOWS cross-matrix."""
    model_config = ConfigDict(extra="ignore")
    SO: List[TOWSStrategy] = Field(default_factory=list)
    ST: List[TOWSStrategy] = Field(default_factory=list)
    WO: List[TOWSStrategy] = Field(default_factory=list)
    WT: List[TOWSStrategy] = Field(default_factory=list)


class PriorityAction(BaseModel):
    """A ranked, ownable action derived from one or more TOWS strategies."""
    model_config = ConfigDict(extra="ignore")
    action_id: str
    title: str
    description: str
    linked_strategy_ids: List[str] = Field(default_factory=list)
    horizon: str
    owner_area: str
    priority_rank: int
    confidence: str
    effort: str
    impact: str
    success_metric: str
    requires_manual_review: bool = False
    blocked_by: List[str] = Field(default_factory=list)


class ResourceAssessmentEntry(BaseModel):
    """Effort × impact grid entry."""
    model_config = ConfigDict(extra="ignore")
    action_id: str
    title: str
    effort: str
    impact: str
    horizon: str
    quadrant_label: str  # quick_win|major_bet|fill_in|thankless


class CampaignBriefFeedItem(BaseModel):
    """Item passed to Campaign Planner. Only confirmed/probable strategies included."""
    model_config = ConfigDict(extra="ignore")
    feed_id: str
    source_strategy_id: str
    source_swot_item_ids: List[str] = Field(default_factory=list)
    campaign_angle: str
    messaging_pillar: str
    channel_suitability: List[str] = Field(default_factory=list)
    confidence: str
    requires_human_approval: bool = False


class StrategyQualityReport(BaseModel):
    """Quality gate output — mirrors the SWOT QualityReport discipline."""
    model_config = ConfigDict(extra="ignore")
    unanchored_strategies: List[str] = Field(default_factory=list)
    overconfident_claims: List[str] = Field(default_factory=list)
    empty_tows_cells: List[str] = Field(default_factory=list)
    manual_review_gates: List[str] = Field(default_factory=list)
    benchmark_language_violations: List[str] = Field(default_factory=list)
    overall_status: str = "PASS"
    warnings: List[str] = Field(default_factory=list)


class StrategyOutput(BaseModel):
    """Top-level output of the Strategy Agent."""
    model_config = ConfigDict(extra="ignore")
    business_type: str = "unknown"
    engine_version: str = ENGINE_VERSION
    strategic_posture: str = StrategicPosture.BALANCED
    posture_rationale: str = ""
    tows_matrix: TOWSMatrix = Field(default_factory=TOWSMatrix)
    priority_action_plan: List[PriorityAction] = Field(default_factory=list)
    resource_assessment: List[ResourceAssessmentEntry] = Field(default_factory=list)
    campaign_brief_feed: List[CampaignBriefFeedItem] = Field(default_factory=list)
    strategy_quality_report: StrategyQualityReport = Field(default_factory=StrategyQualityReport)
    meta: Dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# INPUT FILTERING — enforces should_feed_strategy_agent at the Python layer
# ===========================================================================
def _as_dict(item: Any) -> Dict[str, Any]:
    """Coerce a Pydantic v2 model or dict to a plain dict."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if isinstance(item, dict):
        return item
    # Best-effort fallback
    try:
        return dict(item)  # type: ignore[arg-type]
    except Exception:
        return {}


def _eligible(item: Any) -> bool:
    """An item is eligible if its should_feed_strategy_agent flag is true."""
    d = _as_dict(item)
    return bool(d.get("should_feed_strategy_agent", False))


def filter_strategy_inputs(swot_output: Any) -> dict:
    """
    Extract only the fields the strategy agent is authorized to use.

    Enforces should_feed_strategy_agent gating at the Python layer,
    BEFORE the LLM sees any data.

    Edge cases:
      - If swot_output is a dict (e.g. loaded from JSON), works the same.
      - Missing fields default to empty lists / safe values.
    """
    sd = _as_dict(swot_output)
    swot_report = sd.get("swot_report", {}) or {}
    matrix_outputs = sd.get("matrix_outputs", {}) or {}
    strategic_context = sd.get("strategic_context", {}) or {}
    quality_report = sd.get("quality_report", {}) or {}
    validation_results = sd.get("validation_results", {}) or {}

    def _filter(items: List[Any]) -> List[dict]:
        return [_as_dict(i) for i in (items or []) if _eligible(i)]

    return {
        "strengths":     _filter(swot_report.get("strengths", [])),
        "weaknesses":    _filter(swot_report.get("weaknesses", [])),
        "opportunities": _filter(swot_report.get("opportunities", [])),
        "threats":       _filter(swot_report.get("threats", [])),
        "derived_opportunities": _filter(sd.get("derived_opportunities", [])),
        "directional_competitive_signals": _filter(
            sd.get("directional_competitive_signals", [])
        ),
        "strategic_summary": _as_dict(sd.get("strategic_summary", {})),
        "matrix_outputs":    matrix_outputs,
        "strategic_context": strategic_context,
        "quality_report":    quality_report,
        "validation_status": validation_results.get("overall_status", "UNKNOWN"),
        "benchmark_quality": strategic_context.get("benchmark_quality", "unavailable"),
        "manual_review_ids": [
            (_as_dict(r).get("item_id") or "")
            for r in (quality_report.get("manual_review_needed", []) or [])
            if _as_dict(r).get("item_id")
        ],
        "low_confidence_ids": [
            (_as_dict(r).get("item_id") or "")
            for r in (quality_report.get("low_confidence_items", []) or [])
            if _as_dict(r).get("item_id")
        ],
    }


# ===========================================================================
# SYSTEM PROMPT (module-level constant)
# ===========================================================================
STRATEGY_SYSTEM_PROMPT = dedent("""
    You are STRATEGY-AGENT-v1, a precision business strategy synthesiser.

    You are Stage 5 in an automated marketing intelligence pipeline:
        SWOT v7.0 → [YOU] → Brief Generator → Campaign Planner → Creative/Content Agents

    Your upstream agent (SWOT v7.0) has already done the heavy lifting:
    classified sentiment, scored items, detected semantic overlaps, flagged
    low-confidence signals, and applied claim-strength ceilings. Your job is
    to SYNTHESISE that output into actionable strategies — never to re-analyse
    the raw data, never to introduce new business observations.

    ══════════════════════════════════════════════════════════
    PHASE 1 — INPUT VALIDATION (do this silently, before any output)
    ══════════════════════════════════════════════════════════

    Before generating any strategy:

    1. Confirm `validation_status == "PASS"`. If FAIL → return a StrategyOutput
       with strategic_posture="BLOCKED", all lists empty, and strategy_quality_report
       explaining the blockage. Do not attempt to generate strategies on invalid SWOT data.

    2. Read `benchmark_quality`. Set your CLAIM STRENGTH CEILING for this run:
       - "high"        → confirmed competitive claims allowed
       - "medium"      → cautious competitive language; note sample size
       - "low"         → directional-only; prefix comparisons with
                         "available data suggests..." or "directionally..."
       - "unavailable" → NO competitive comparisons whatsoever;
                         every competitive-facing claim must be removed or
                         replaced with an internal-only observation

    3. Index `manual_review_ids` and `low_confidence_ids`. Any strategy built
       on these item_ids MUST set `requires_manual_review: true` and
       `downstream_campaign_eligible: false`.

    4. Index the three matrices:
       - importance_performance_matrix → drives SO/ST priority weighting
       - opportunity_threat_matrix     → drives confidence and horizon assignment
       - vulnerability_matrix         → items here are URGENT; ST strategies
                                        anchored on these get horizon = "immediate"

    ══════════════════════════════════════════════════════════
    PHASE 2 — STRATEGIC POSTURE CLASSIFICATION
    ══════════════════════════════════════════════════════════

    Classify the business's strategic posture from these rules (apply in order;
    first match wins):

    LEVERAGE_LED:
      - strengths count ≥ 2 AND (opportunities count ≥ 1 OR derived_opportunities count ≥ 1)
      - No validated weaknesses
      - Top strength has strategic_priority ≥ 8.0
      → Frame: "Leverage core advantages to capture available opportunities aggressively."

    DEFENSE_LED:
      - threats count ≥ 1 AND any threat has vulnerability_score ≥ 6.0
      - strengths count ≥ 2 (sufficient to defend)
      → Frame: "Protect validated strengths while neutralising the highest-vulnerability threat."

    IMPROVEMENT_LED:
      - weaknesses count ≥ 2 AND opportunities count ≥ 1
      → Frame: "Close priority capability gaps to become eligible for existing opportunities."

    CONTINGENCY_LED:
      - weaknesses count ≥ 1 AND threats count ≥ 1 AND strengths count ≤ 1
      → Frame: "Stabilise the business by reducing exposure on both internal and external fronts."

    BALANCED:
      - None of the above; all quadrants have items but no dominant signal
      → Frame: "Pursue a balanced programme: sustain strengths, monitor risks, and test opportunities."

    Populate `strategic_posture` (the enum key) and `posture_rationale`
    (2–3 sentences explaining the data that drove this classification).

    ══════════════════════════════════════════════════════════
    PHASE 3 — TOWS MATRIX GENERATION
    ══════════════════════════════════════════════════════════

    The TOWS matrix maps SWOT quadrant PAIRS to concrete strategic directions:

      SO (Strength × Opportunity)  — Use strengths to capture opportunities
      ST (Strength × Threat)       — Use strengths to neutralise threats
      WO (Weakness × Opportunity)  — Improve weaknesses to pursue opportunities
      WT (Weakness × Threat)       — Defend against the worst-case collision

    GENERATION RULES:

    A. PAIRING LOGIC
       - For SO: pair each Opportunity with the highest-priority Strength
         that plausibly addresses the same customer dimension.
       - For ST: pair each Threat with the Strength whose tags overlap most
         with the threat's theme.
       - For WO: pair each Weakness with the Opportunity it blocks access to.
       - For WT: pair each Weakness with the Threat that most amplifies it.
       - If derived_opportunities exist, they may supplement SO strategies
         (they are already Strength-derived; mark `confidence: probable`).
       - If there are no weaknesses, produce ONE WT strategy using the
         watchout item as a proxy, marked `confidence: watchout_only` and
         `requires_manual_review: true`.
       - If a cell has no valid item pairs, leave the list empty and log it
         in strategy_quality_report.empty_tows_cells with a reason.

    B. STRATEGY CONSTRUCTION (per TOWSStrategy)
       - `strategy_id`: format "{TYPE}_{zero-padded 2-digit number}", e.g. "SO_01"
       - `title`: ≤ 12 words; action-oriented, specific to this business
       - `description`: 2–4 sentences. MUST cite the specific SWOT anchors by name
         (not item_id; use the item title). Ground every claim in evidence.
       - `rationale`: 1–2 sentences. Explain WHY this pairing is strategically sound.
       - `anchors`: list of StrategyAnchor for every SWOT item driving this strategy
       - `confidence`: the MINIMUM claim_strength across all anchors, mapped to:
           validated              → "confirmed"
           internally_supported   → "probable"
           directional_not_valid  → "exploratory"
           early_warning          → "watchout_only"
       - `horizon`: assign using these rules:
           - Any anchor in vulnerability_matrix with score ≥ 6 → "immediate"
           - SO strategies with top-priority strength (sp ≥ 8) → "short_term"
           - WO strategies (capability gap must be closed first) → "medium_term"
           - WT strategies with exploratory/watchout confidence → "long_term"
           - All other cases → "short_term" as default
       - `estimated_effort`: low / medium / high. Use this heuristic:
           - Internal brand or marketing action = low
           - Operations or process change = medium
           - Product development or pricing restructure = high
       - `estimated_impact`: derive from the anchor's `strategic_priority` score:
           sp ≥ 8.0 → high; 5.0–7.9 → medium; < 5.0 → low
       - `downstream_campaign_eligible`: true only if confidence ∈ {confirmed, probable}
         AND requires_manual_review == false
       - `watchout_flag`: if confidence ∈ {exploratory, watchout_only}, populate
         with a 1-sentence user-facing warning explaining the data limitation.

    C. QUANTITY LIMITS
       Max strategies per TOWS cell:
         SO: 3   ST: 2   WO: 2   WT: 2   (total ≤ 9)

    D. NO DUPLICATION
       - No two strategies across any cell may describe the same underlying action.
       - If a strength anchors both an SO and an ST strategy, the descriptions
         must be clearly differentiated (Grow vs. Defend angle).

    E. LANGUAGE DISCIPLINE
       - If benchmark_quality ∈ {"unavailable", "low"}, the following phrases
         are BANNED in all descriptions:
             "outperforms", "beats", "ahead of", "dominates competitors",
             "market leader", "superior to rivals", "best in category"
         Replace with: "shows a favorable internal signal", "holds a
         directional advantage in available data", "positioned to differentiate
         based on customer feedback"
       - Never reference item_ids in user-facing text (descriptions, titles).
         Item_ids only appear inside the `anchors` array.

    ══════════════════════════════════════════════════════════
    PHASE 4 — PRIORITY ACTION PLAN
    ══════════════════════════════════════════════════════════

    Derive a flat, ordered Priority Action Plan from the TOWS strategies.

    RULES:
    1. Each PriorityAction must link to ≥ 1 strategy_id via `linked_strategy_ids`.
    2. One TOWS strategy may generate multiple actions if it has distinct owner areas.
    3. Rank globally by: urgency_score = (impact_weight × confidence_weight) / effort_weight
       where: high=3, medium=2, low=1 for impact/effort; confirmed=1.0, probable=0.8,
       exploratory=0.5, watchout_only=0.2 for confidence_weight.
    4. `horizon` must match or be longer than the source strategy's horizon.
    5. `owner_area` mapping:
         - "marketing"   : campaigns, brand positioning, social, content
         - "operations"  : service, speed, cleanliness, staff training
         - "product"     : menu, pricing, value engineering
         - "management"  : pricing policy, competitive monitoring, data collection
         - "multi"       : cross-functional; requires cross-team coordination
    6. `success_metric`: must be concrete and measurable, e.g.:
         - "Maintain food quality rating ≥ 4.5 stars over next 3 months"
         - "Reduce pricing-gap mentions in reviews by 20% in 6 months"
         - NOT acceptable: "Improve customer satisfaction"
    7. `blocked_by`: populate if an action assumes another action is already complete.
    8. Actions derived from `manual_review_needed` items must set
       `requires_manual_review: true` and appear at the END of the list
       regardless of rank score.

    Maximum PriorityActions: 8

    ══════════════════════════════════════════════════════════
    PHASE 5 — RESOURCE ASSESSMENT GRID
    ══════════════════════════════════════════════════════════

    For every PriorityAction, produce one ResourceAssessmentEntry.

    `quadrant_label` classification:
      - effort=low  × impact=high  → "quick_win"
      - effort=high × impact=high  → "major_bet"
      - effort=low  × impact=low   → "fill_in"
      - effort=high × impact=low   → "thankless"
      - effort=medium (any)        → use the impact to determine:
          impact=high → "quick_win" if horizon ≤ short_term, else "major_bet"
          impact=low  → "fill_in"

    This grid is consumed by the Brief Generator to allocate budgets.

    ══════════════════════════════════════════════════════════
    PHASE 6 — CAMPAIGN BRIEF FEED
    ══════════════════════════════════════════════════════════

    The Campaign Brief Feed is the contract between the Strategy Agent and
    the Campaign Planner. It contains ONLY strategies that are:
      - `downstream_campaign_eligible: true`
      - `confidence ∈ {confirmed, probable}`
      - `requires_manual_review: false`

    For each eligible TOWSStrategy, produce one CampaignBriefFeedItem:

    `campaign_angle`:
      A single, specific creative hook sentence (≤ 20 words).
      Example: "Your café's food quality is rated near-perfect — make that
      the hero of every post."
      NOT acceptable: "Promote the business online."

    `messaging_pillar`:
      The brand value claim this strategy activates. Examples:
      - "Quality Assurance" (for food quality strengths)
      - "Comfort & Atmosphere" (for ambience advantage)
      - "Local Trust" (for service + location cluster)

    `channel_suitability`:
      Select from: ["social_organic", "paid_social", "email", "in_store", "pr", "search"]
      Base suitability on the source strategy's tags and owner_area.

    `requires_human_approval`:
      true if any source SWOT item is in `manual_review_ids`.
      This flag tells the Campaign Planner to queue the item for human sign-off
      before executing any creative.

    Maximum CampaignBriefFeedItems: 5

    ══════════════════════════════════════════════════════════
    PHASE 7 — STRATEGY QUALITY REPORT
    ══════════════════════════════════════════════════════════

    After generating all output, run these checks:

    CHECK 1 — unanchored_strategies:
      Any strategy_id where `anchors` is empty or contains only invalid item_ids.

    CHECK 2 — overconfident_claims:
      Scan all `description` and `title` fields for banned language
      (see Phase 3E). Report any violations.

    CHECK 3 — empty_tows_cells:
      List any TOWS cell (SO|ST|WO|WT) that produced 0 strategies.
      Include the reason: "no_weaknesses", "no_opportunities", "no_validated_pairs", etc.

    CHECK 4 — manual_review_gates:
      List all item_ids that are in `manual_review_ids` and are used as anchors
      in any strategy. These are the gating items before campaigns can run.

    CHECK 5 — benchmark_language_violations:
      If benchmark_quality ∈ {"unavailable", "low"}, report any strategy_id
      whose description contains absolute competitive comparisons.

    `overall_status`:
      - "FAIL" if CHECK 1 or CHECK 5 has any entries
      - "WARN" if CHECK 2, 3, or 4 has entries but CHECK 1 and 5 are clean
      - "PASS" if all checks are empty

    ══════════════════════════════════════════════════════════
    HARD OUTPUT CONSTRAINTS
    ══════════════════════════════════════════════════════════

    • Output STRICT JSON matching the StrategyOutput schema. No prose, no markdown.
    • Schema:
        {
          "business_type": "...",
          "engine_version": "1.0",
          "strategic_posture": "...",
          "posture_rationale": "...",
          "tows_matrix": {
            "SO": [TOWSStrategy, ...],
            "ST": [TOWSStrategy, ...],
            "WO": [TOWSStrategy, ...],
            "WT": [TOWSStrategy, ...]
          },
          "priority_action_plan": [PriorityAction, ...],
          "resource_assessment": [ResourceAssessmentEntry, ...],
          "campaign_brief_feed": [CampaignBriefFeedItem, ...],
          "strategy_quality_report": StrategyQualityReport,
          "meta": {}
        }

    • All list fields default to [] if no eligible items; never null.
    • strategy_id, action_id, feed_id must be unique within their list.
    • item_ids in anchors must exactly match item_id values from the input.
    • No fabricated observations — every claim traces to a named input field.
    • Be conservative. Be evidence-driven. Output JSON only.
""").strip()


# ===========================================================================
# USER PROMPT BUILDER
# ===========================================================================
def build_strategy_user_prompt(filtered_inputs: dict) -> str:
    """
    Construct the user prompt for the Strategy Agent.

    Takes the output of filter_strategy_inputs() and produces a slimmed,
    JSON-formatted prompt that surfaces only the fields the LLM should
    reason about. Includes a benchmark notice and a quick posture hint.
    """

    def slim_item(item: dict) -> dict:
        return {
            "item_id":             item.get("item_id") or item.get("watchout_id") or item.get("signal_id"),
            "quadrant":            item.get("quadrant", ""),
            "title":               item.get("title", ""),
            "source_theme":        item.get("source_theme", ""),
            "tags":                item.get("tags", []),
            "claim_strength":      item.get("claim_strength", ""),
            "strategic_priority":  (item.get("scoring") or {}).get("strategic_priority", 0),
            "confidence":          (item.get("scoring") or {}).get("confidence", 0),
            "pi_zone":             item.get("pi_zone", ""),
            "vulnerability_score": item.get("vulnerability_score"),
            "manual_review_only":  item.get("manual_review_only", False),
            "reasoning_summary":   (item.get("reasoning", "") or "")[:300],
        }

    matrix_outputs = filtered_inputs.get("matrix_outputs", {}) or {}

    payload = {
        "benchmark_quality":             filtered_inputs["benchmark_quality"],
        "validation_status":             filtered_inputs["validation_status"],
        "manual_review_ids":             filtered_inputs["manual_review_ids"],
        "low_confidence_ids":            filtered_inputs["low_confidence_ids"],
        "strengths":                     [slim_item(i) for i in filtered_inputs["strengths"]],
        "weaknesses":                    [slim_item(i) for i in filtered_inputs["weaknesses"]],
        "opportunities":                 [slim_item(i) for i in filtered_inputs["opportunities"]],
        "threats":                       [slim_item(i) for i in filtered_inputs["threats"]],
        "derived_opportunities":         [slim_item(i) for i in filtered_inputs["derived_opportunities"]],
        "directional_signals":           [slim_item(i) for i in filtered_inputs["directional_competitive_signals"]],
        "importance_performance_matrix": matrix_outputs.get("importance_performance_matrix", []),
        "opportunity_threat_matrix":     matrix_outputs.get("opportunity_threat_matrix", []),
        "vulnerability_matrix":          matrix_outputs.get("vulnerability_matrix", []),
        "strategic_summary":             filtered_inputs["strategic_summary"],
    }

    quadrant_counts = {
        "S": len(filtered_inputs["strengths"]),
        "W": len(filtered_inputs["weaknesses"]),
        "O": len(filtered_inputs["opportunities"]),
        "T": len(filtered_inputs["threats"]),
    }

    posture_hint = (
        f"S={quadrant_counts['S']} W={quadrant_counts['W']} "
        f"O={quadrant_counts['O']} T={quadrant_counts['T']} — "
        + (
            "strength-heavy profile; likely LEVERAGE_LED or DEFENSE_LED."
            if quadrant_counts["S"] >= 2 and quadrant_counts["W"] == 0
            else "mixed profile; apply posture rules carefully."
        )
    )

    benchmark_notice = {
        "unavailable": (
            "⚠ BENCHMARK UNAVAILABLE — No competitor data was collected. "
            "All strategies must be framed purely in terms of internal performance "
            "and internal customer feedback. No competitive comparisons permitted."
        ),
        "low": (
            "⚠ BENCHMARK LOW QUALITY — Competitor data is present but thin. "
            "Use directional language only. No absolute comparisons."
        ),
        "medium": (
            "ℹ BENCHMARK MEDIUM QUALITY — Treat comparative claims with caution. "
            "Note sample size limitations where relevant."
        ),
        "high": (
            "✓ BENCHMARK HIGH QUALITY — Competitive comparisons are permitted "
            "with normal confidence."
        ),
    }.get(filtered_inputs["benchmark_quality"], "")

    user_prompt = dedent(f"""
        Synthesise the following SWOT output into a complete StrategyOutput.

        BENCHMARK NOTICE:
        {benchmark_notice}

        POSTURE HINT (for Phase 2 classification):
        {posture_hint}

        CRITICAL ITEM FLAGS:
        - Items requiring manual review (never anchor a confirmed strategy on these):
          {filtered_inputs['manual_review_ids']}
        - Items with low confidence score (use hedged language):
          {filtered_inputs['low_confidence_ids']}

        PROCEED THROUGH ALL 7 PHASES in order. Apply each phase's rules strictly.

        SWOT DATA:
        {json.dumps(payload, indent=2, default=str)}

        Return JSON only. No prose. No markdown fences. No item_ids in user-facing text.
    """).strip()

    return user_prompt


# ===========================================================================
# POST-PROCESSOR
# ===========================================================================
class StrategyPostProcessor:
    """
    Post-LLM validation, gating, and quality enforcement.

    Mirrors the SWOT v7.0 post-processor discipline:
      • Verify every anchor's item_id exists in the SWOT output.
      • Scan for banned competitive language when benchmark quality is low.
      • Override LLM safety fields when an anchor is in manual_review_ids.
      • Clamp counts to per-cell and total limits.
      • Recompute the StrategyQualityReport from scratch.
    """

    BANNED_COMPETITIVE_PHRASES = [
        "outperforms",
        "beats",
        "ahead of",
        "dominates competitors",
        "market leader",
        "superior to rivals",
        "best in category",
        "number one",
        "leading competitor",
        "far exceeds",
    ]

    # ---- CHECK 1 -----------------------------------------------------------
    def validate_anchors(self, output: StrategyOutput, valid_item_ids: set) -> List[str]:
        """Verify all anchor item_ids exist in the SWOT output."""
        violations: List[str] = []
        for s in self._all_strategies(output):
            if not s.anchors:
                violations.append(f"{s.strategy_id}: no anchors provided")
                continue
            for anchor in s.anchors:
                if anchor.item_id not in valid_item_ids:
                    violations.append(
                        f"{s.strategy_id}: anchor '{anchor.item_id}' not in SWOT output"
                    )
        return violations

    # ---- CHECK 5 -----------------------------------------------------------
    def scan_banned_language(
        self, output: StrategyOutput, benchmark_quality: str
    ) -> List[str]:
        """Language discipline enforcement when benchmark is unavailable/low."""
        if benchmark_quality in ("high", "medium"):
            return []
        violations: List[str] = []
        for s in self._all_strategies(output):
            text = f"{s.description} {s.title}".lower()
            for phrase in self.BANNED_COMPETITIVE_PHRASES:
                if phrase in text:
                    violations.append(
                        f"{s.strategy_id}: banned phrase '{phrase}' in description"
                    )
        return violations

    # ---- Gate enforcement --------------------------------------------------
    def enforce_manual_review_gates(
        self, output: StrategyOutput, manual_review_ids: List[str]
    ) -> StrategyOutput:
        """
        Ensure any strategy anchored on a manual_review item has
        requires_manual_review=True and downstream_campaign_eligible=False.

        Also enforces the global rule:
          downstream_campaign_eligible == True ONLY IF
            confidence ∈ {confirmed, probable} AND requires_manual_review == False
        """
        mr_set = set(manual_review_ids or [])
        for s in self._all_strategies(output):
            anchor_ids = [a.item_id for a in s.anchors]
            if any(aid in mr_set for aid in anchor_ids):
                s.requires_manual_review = True
                s.downstream_campaign_eligible = False

            # Hard rule enforcement on downstream_campaign_eligible
            confidence_ok = s.confidence in (
                StrategyConfidence.CONFIRMED,
                StrategyConfidence.PROBABLE,
            )
            if not confidence_ok or s.requires_manual_review:
                s.downstream_campaign_eligible = False
        return output

    # ---- Quantity caps -----------------------------------------------------
    def clamp_strategy_counts(self, output: StrategyOutput) -> StrategyOutput:
        """Enforce max strategies per TOWS cell and per top-level list."""
        output.tows_matrix.SO = output.tows_matrix.SO[:MAX_SO_STRATEGIES]
        output.tows_matrix.ST = output.tows_matrix.ST[:MAX_ST_STRATEGIES]
        output.tows_matrix.WO = output.tows_matrix.WO[:MAX_WO_STRATEGIES]
        output.tows_matrix.WT = output.tows_matrix.WT[:MAX_WT_STRATEGIES]
        output.priority_action_plan = output.priority_action_plan[:MAX_PRIORITY_ACTIONS]
        output.campaign_brief_feed = output.campaign_brief_feed[:MAX_CAMPAIGN_FEED_ITEMS]
        return output

    # ---- Sanitize Campaign Brief Feed -------------------------------------
    def sanitize_campaign_feed(
        self, output: StrategyOutput, manual_review_ids: List[str]
    ) -> StrategyOutput:
        """
        Drop CampaignBriefFeedItems whose source strategy is not downstream-eligible
        or whose source SWOT item is in manual_review_ids.
        """
        mr_set = set(manual_review_ids or [])
        strategy_index = {s.strategy_id: s for s in self._all_strategies(output)}
        cleaned: List[CampaignBriefFeedItem] = []
        for item in output.campaign_brief_feed:
            parent = strategy_index.get(item.source_strategy_id)
            # Drop items with no matching parent strategy
            if parent is None:
                continue
            # Drop items whose parent is ineligible
            if not parent.downstream_campaign_eligible:
                continue
            # Enforce confidence floor
            if parent.confidence not in (
                StrategyConfidence.CONFIRMED, StrategyConfidence.PROBABLE
            ):
                continue
            # Flag for human approval if any source SWOT item needs manual review
            if any(sid in mr_set for sid in item.source_swot_item_ids):
                item.requires_human_approval = True
                # Per spec: manual_review_only items must NOT appear in campaign feed
                continue
            cleaned.append(item)
        output.campaign_brief_feed = cleaned
        return output

    # ---- Resource assessment back-fill ------------------------------------
    def ensure_resource_assessment(self, output: StrategyOutput) -> StrategyOutput:
        """
        Guarantee every PriorityAction has a matching ResourceAssessmentEntry,
        and that each entry has a quadrant_label.
        """
        existing_ids = {r.action_id for r in output.resource_assessment}
        for action in output.priority_action_plan:
            if action.action_id in existing_ids:
                continue
            output.resource_assessment.append(
                ResourceAssessmentEntry(
                    action_id=action.action_id,
                    title=action.title,
                    effort=action.effort or "medium",
                    impact=action.impact or "medium",
                    horizon=action.horizon or StrategyHorizon.SHORT_TERM,
                    quadrant_label=self._quadrant_label(
                        action.effort, action.impact, action.horizon
                    ),
                )
            )
        # Re-label any entries missing a quadrant_label
        for r in output.resource_assessment:
            if not r.quadrant_label:
                r.quadrant_label = self._quadrant_label(r.effort, r.impact, r.horizon)
        return output

    @staticmethod
    def _quadrant_label(effort: str, impact: str, horizon: str) -> str:
        """Effort × impact grid classifier."""
        e = (effort or "medium").lower()
        i = (impact or "medium").lower()
        h = (horizon or "short_term").lower()
        if e == "low" and i == "high":
            return "quick_win"
        if e == "high" and i == "high":
            return "major_bet"
        if e == "low" and i == "low":
            return "fill_in"
        if e == "high" and i == "low":
            return "thankless"
        # medium effort branches
        if e == "medium":
            if i == "high":
                return "quick_win" if h in (
                    StrategyHorizon.IMMEDIATE, StrategyHorizon.SHORT_TERM
                ) else "major_bet"
            if i == "low":
                return "fill_in"
        # medium impact, low/high effort
        if i == "medium":
            return "quick_win" if e == "low" else "major_bet"
        return "fill_in"

    # ---- Quality report (recomputed) --------------------------------------
    def re_run_quality_report(
        self,
        output: StrategyOutput,
        valid_item_ids: set,
        benchmark_quality: str,
        manual_review_ids: List[str],
    ) -> StrategyOutput:
        """Recompute quality report from scratch after post-processing."""
        anchor_violations = self.validate_anchors(output, valid_item_ids)
        language_violations = self.scan_banned_language(output, benchmark_quality)

        empty_cells: List[str] = []
        cell_map = {
            "SO": output.tows_matrix.SO,
            "ST": output.tows_matrix.ST,
            "WO": output.tows_matrix.WO,
            "WT": output.tows_matrix.WT,
        }
        for cell, strategies in cell_map.items():
            if not strategies:
                empty_cells.append(cell)

        mr_set = set(manual_review_ids or [])
        used_manual: List[str] = []
        for s in self._all_strategies(output):
            for anchor in s.anchors:
                if anchor.item_id in mr_set:
                    used_manual.append(anchor.item_id)
        used_manual = sorted(set(used_manual))

        # Status logic per Phase 7
        if anchor_violations or language_violations:
            overall = "FAIL"
        elif empty_cells or used_manual:
            overall = "WARN"
        else:
            overall = "PASS"

        warnings: List[str] = []
        warnings.extend(f"Empty TOWS cell: {c}" for c in empty_cells)
        warnings.extend(f"Manual review gate: {m}" for m in used_manual)
        warnings.extend(f"Anchor violation: {v}" for v in anchor_violations)
        warnings.extend(f"Language violation: {v}" for v in language_violations)

        output.strategy_quality_report = StrategyQualityReport(
            unanchored_strategies=anchor_violations,
            overconfident_claims=[],  # captured inside benchmark_language_violations
            empty_tows_cells=empty_cells,
            manual_review_gates=used_manual,
            benchmark_language_violations=language_violations,
            overall_status=overall,
            warnings=warnings,
        )
        return output

    # ---- Helpers -----------------------------------------------------------
    @staticmethod
    def _all_strategies(output: StrategyOutput) -> List[TOWSStrategy]:
        return (
            list(output.tows_matrix.SO)
            + list(output.tows_matrix.ST)
            + list(output.tows_matrix.WO)
            + list(output.tows_matrix.WT)
        )

    # ---- Orchestration -----------------------------------------------------
    def run(
        self,
        output: StrategyOutput,
        valid_item_ids: set,
        benchmark_quality: str,
        manual_review_ids: List[str],
    ) -> StrategyOutput:
        """Run all post-processing stages in the correct order."""
        output = self.enforce_manual_review_gates(output, manual_review_ids)
        output = self.clamp_strategy_counts(output)
        output = self.sanitize_campaign_feed(output, manual_review_ids)
        output = self.ensure_resource_assessment(output)
        output = self.re_run_quality_report(
            output, valid_item_ids, benchmark_quality, manual_review_ids
        )
        return output


# ===========================================================================
# PIPELINE ORCHESTRATOR
# ===========================================================================
def _blocked_output(swot_output: Any) -> StrategyOutput:
    """Build a BLOCKED StrategyOutput when SWOT validation has failed."""
    sd = _as_dict(swot_output)
    validation = sd.get("validation_results", {}) or {}
    status = validation.get("overall_status", "UNKNOWN")
    violations = validation.get("violations", []) or []
    return StrategyOutput(
        business_type=sd.get("business_type", "unknown"),
        engine_version=ENGINE_VERSION,
        strategic_posture=StrategicPosture.BLOCKED,
        posture_rationale=(
            f"SWOT validation status is {status}. "
            f"Violations: {violations}. "
            "Strategy generation blocked until SWOT output passes validation."
        ),
        tows_matrix=TOWSMatrix(),
        priority_action_plan=[],
        resource_assessment=[],
        campaign_brief_feed=[],
        strategy_quality_report=StrategyQualityReport(
            overall_status="FAIL",
            warnings=["SWOT validation FAIL — strategy generation blocked."],
        ),
        meta={
            "engine_version": ENGINE_VERSION,
            "blocked_reason": "swot_validation_fail",
            "validation_status": status,
        },
    )


def _dry_run_output(swot_output: Any, filtered: dict, elapsed_ms: int) -> StrategyOutput:
    """Placeholder StrategyOutput for pipeline testing (no LLM call)."""
    sd = _as_dict(swot_output)
    return StrategyOutput(
        business_type=sd.get("business_type", "unknown"),
        engine_version=ENGINE_VERSION,
        strategic_posture=StrategicPosture.LEVERAGE_LED,
        posture_rationale="[DRY RUN — LLM not called]",
        tows_matrix=TOWSMatrix(),
        priority_action_plan=[],
        resource_assessment=[],
        campaign_brief_feed=[],
        strategy_quality_report=StrategyQualityReport(
            overall_status="PASS",
            warnings=["dry_run mode — no LLM output generated"],
        ),
        meta={
            "engine_version": ENGINE_VERSION,
            "dry_run": True,
            "benchmark_quality": filtered.get("benchmark_quality", "unavailable"),
            "validation_status": filtered.get("validation_status", "UNKNOWN"),
            "processing_time_ms": elapsed_ms,
        },
    )


def _collect_valid_item_ids(filtered: dict) -> set:
    """Build the set of all known anchor item_ids the LLM is allowed to use."""
    ids: set = set()
    for quad in ("strengths", "weaknesses", "opportunities", "threats"):
        for it in filtered.get(quad, []) or []:
            iid = it.get("item_id")
            if iid:
                ids.add(iid)
    for d in filtered.get("derived_opportunities", []) or []:
        iid = d.get("item_id")
        if iid:
            ids.add(iid)
    for s in filtered.get("directional_competitive_signals", []) or []:
        sid = s.get("signal_id") or s.get("item_id")
        if sid:
            ids.add(sid)
    return ids


def run_strategy_agent(
    swot_output: Any,
    llm_client: Any,
    dry_run: bool = False,
) -> StrategyOutput:
    """
    Stage 5 entry point. Called by the pipeline orchestrator after SWOT v7.0 completes.

    Args:
        swot_output: A SWOTOutput Pydantic model (or equivalent dict) from Stage 4.
        llm_client:  An LLMClient instance (or a chain list) compatible with
                     swot_agent_v7_0.call_llm_chain.
        dry_run:     If True, returns a placeholder StrategyOutput without LLM call.

    Returns:
        A fully post-processed StrategyOutput ready to pass to the Brief Generator.

    Edge cases:
        - If SWOT validation_status != PASS, returns a BLOCKED output.
        - If all LLM providers fail, raises RuntimeError.
        - If LLM returns malformed JSON, returns an empty StrategyOutput with a
          FAIL quality report (anchor validation will catch the empty matrix).
    """
    start = time.time()

    # Pre-flight: abort on invalid SWOT
    sd = _as_dict(swot_output)
    validation = sd.get("validation_results", {}) or {}
    if validation.get("overall_status") != "PASS":
        logger.warning(
            "SWOT validation status != PASS (was %r) — emitting BLOCKED output.",
            validation.get("overall_status"),
        )
        out = _blocked_output(swot_output)
        out.meta["processing_time_ms"] = int((time.time() - start) * 1000)
        return out

    # Stage 1 — Filter inputs (Python-layer gating)
    filtered = filter_strategy_inputs(swot_output)
    valid_item_ids = _collect_valid_item_ids(filtered)

    # Dry-run short-circuit
    if dry_run:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("Strategy Agent dry-run — returning placeholder output in %dms.", elapsed_ms)
        return _dry_run_output(swot_output, filtered, elapsed_ms)

    # Stage 2 — Build prompts
    user_prompt = build_strategy_user_prompt(filtered)

    # Stage 3 — LLM call (accept either a single client or an already-built chain)
    if isinstance(llm_client, list):
        chain = llm_client
    else:
        chain = [llm_client]

    logger.info("Strategy Agent calling LLM (chain size=%d)…", len(chain))
    raw_response, client_used = call_llm_chain(
        chain=chain,
        system=STRATEGY_SYSTEM_PROMPT,
        user=user_prompt,
    )
    if not raw_response:
        raise RuntimeError("Strategy Agent: all LLM providers failed.")

    # Stage 4 — Parse JSON safely
    raw_dict = safe_parse_json(raw_response)
    if not raw_dict:
        logger.error("Strategy Agent: LLM returned unparseable JSON.")
        out = StrategyOutput(
            business_type=sd.get("business_type", "unknown"),
            engine_version=ENGINE_VERSION,
            strategic_posture=StrategicPosture.BALANCED,
            posture_rationale="LLM returned unparseable output; falling back to empty matrix.",
            strategy_quality_report=StrategyQualityReport(
                overall_status="FAIL",
                warnings=["LLM JSON parse failure — no strategies generated."],
            ),
        )
        out.meta = {
            "engine_version": ENGINE_VERSION,
            "llm_provider_used": getattr(client_used, "provider_name", "unknown"),
            "benchmark_quality": filtered["benchmark_quality"],
            "validation_status": filtered["validation_status"],
            "processing_time_ms": int((time.time() - start) * 1000),
            "dry_run": dry_run,
            "parse_failure": True,
        }
        return out

    # Stage 5 — Validate into Pydantic schema
    try:
        strategy_output = StrategyOutput.model_validate(raw_dict)
    except Exception as e:  # noqa: BLE001
        logger.error("Strategy Agent: schema validation failed: %s", e)
        strategy_output = StrategyOutput(
            business_type=sd.get("business_type", "unknown"),
            strategic_posture=StrategicPosture.BALANCED,
            posture_rationale="LLM output failed Pydantic validation; emitting safe defaults.",
            strategy_quality_report=StrategyQualityReport(
                overall_status="FAIL",
                warnings=[f"Schema validation error: {e}"],
            ),
        )

    # Stage 6 — Post-process
    pp = StrategyPostProcessor()
    strategy_output = pp.run(
        strategy_output,
        valid_item_ids=valid_item_ids,
        benchmark_quality=filtered["benchmark_quality"],
        manual_review_ids=filtered["manual_review_ids"],
    )

    # Stage 7 — Meta
    swot_meta = sd.get("meta", {}) or {}
    strategy_output.engine_version = ENGINE_VERSION
    strategy_output.meta = {
        "engine_version": ENGINE_VERSION,
        "llm_provider_used": getattr(client_used, "provider_name", "unknown"),
        "llm_model_used": getattr(client_used, "model_name", "unknown"),
        "benchmark_quality": filtered["benchmark_quality"],
        "validation_status": filtered["validation_status"],
        "processing_time_ms": int((time.time() - start) * 1000),
        "dry_run": dry_run,
        "swot_engine_version": swot_meta.get("engine_version", "unknown"),
    }

    logger.info(
        "Strategy Agent complete: posture=%s status=%s strategies=S%d/T%d/O%d/T%d actions=%d feed=%d in %dms",
        strategy_output.strategic_posture,
        strategy_output.strategy_quality_report.overall_status,
        len(strategy_output.tows_matrix.SO),
        len(strategy_output.tows_matrix.ST),
        len(strategy_output.tows_matrix.WO),
        len(strategy_output.tows_matrix.WT),
        len(strategy_output.priority_action_plan),
        len(strategy_output.campaign_brief_feed),
        strategy_output.meta["processing_time_ms"],
    )

    return strategy_output


# ===========================================================================
# CLI ENTRY POINT (optional convenience)
# ===========================================================================
def _cli_main() -> int:
    """
    Optional CLI: read swot_report.json, run the strategy agent against
    whichever LLM client SWOT v7.0 builds via LLMClientFactory.

    Usage:
        python strategy.py --input swot_report.json --output strategy_report.json \
            [--provider auto] [--model gemini-2.5-flash] [--dry-run]
    """
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(
        description="Strategy Agent v1.0 — Stage 5 of the BI pipeline."
    )
    ap.add_argument("--input", required=True, type=Path, help="Path to swot_report.json")
    ap.add_argument("--output", required=True, type=Path, help="Path to strategy_report.json")
    ap.add_argument("--provider", default="auto", help="LLM provider preference (see SWOT v7.0).")
    ap.add_argument("--model", default=None, help="Override LLM model for chosen provider.")
    ap.add_argument("--dry-run", action="store_true", help="Skip LLM call; emit placeholder.")
    ap.add_argument("--verbose", action="store_true", help="Enable DEBUG logging.")
    args = ap.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    # Load SWOT output
    with args.input.open("r", encoding="utf-8") as f:
        swot_data = json.load(f)
    try:
        swot_obj = SWOTOutput.model_validate(swot_data)  # type: ignore[attr-defined]
    except Exception:
        # If we can't import SWOTOutput from swot_agent_v7_0 in this env,
        # operate on the raw dict — filter_strategy_inputs handles dicts too.
        swot_obj = swot_data  # type: ignore[assignment]

    # Build LLM chain via SWOT v7.0's factory if available
    chain: List[Any] = []
    if not args.dry_run:
        try:
            from swot_agent_v7_0 import LLMClientFactory, LLMProvider  # type: ignore
            chain = LLMClientFactory.build_chain(
                LLMProvider(args.provider), args.model
            )
        except Exception as e:
            logger.error("Could not build LLM chain: %s", e)
            return 2
        if not chain:
            logger.error("No LLM provider available. Use --dry-run for placeholder output.")
            return 2

    try:
        result = run_strategy_agent(swot_obj, chain or None, dry_run=args.dry_run)
    except Exception as e:  # noqa: BLE001
        logger.error("Strategy Agent failed: %s", e)
        import traceback
        traceback.print_exc()
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, default=str)

    print(f"\n✓ Strategy v{ENGINE_VERSION} → {args.output}")
    print(f"  posture: {result.strategic_posture}")
    print(f"  status:  {result.strategy_quality_report.overall_status}")
    print(f"  TOWS:    SO={len(result.tows_matrix.SO)} ST={len(result.tows_matrix.ST)} "
          f"WO={len(result.tows_matrix.WO)} WT={len(result.tows_matrix.WT)}")
    print(f"  actions: {len(result.priority_action_plan)}")
    print(f"  feed:    {len(result.campaign_brief_feed)}")
    return 0 if result.strategy_quality_report.overall_status != "FAIL" else 1


if __name__ == "__main__":
    import sys
    sys.exit(_cli_main())