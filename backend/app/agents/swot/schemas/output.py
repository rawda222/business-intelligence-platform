"""
SWOT Agent v7 - Output Schemas
==============================
Pydantic schemas for the final SWOT report.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.agents.swot.config import ENGINE_VERSION, EVIDENCE_DISPLAY_CAP
from app.agents.swot.enums import ClaimStrength


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
    quadrant: str
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
    severity: str = "low"
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
    direction: str = "advantage"
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
    """Core SWOT quadrants - CONFIRMED items only (no shadows in weaknesses)."""
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
    """FIX 14 - Validation test results."""
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
    """Final SWOT report - top-level object."""
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