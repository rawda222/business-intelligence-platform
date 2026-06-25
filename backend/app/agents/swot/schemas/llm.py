"""
SWOT Agent v7 - LLM Schemas
============================
Smaller semantic-core schemas that LLMs produce.
"""
from typing import Any, List
from pydantic import BaseModel, Field, ConfigDict


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