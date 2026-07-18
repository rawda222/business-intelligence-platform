"""
SWOT Agent v7 - Input Schemas
=============================
Pydantic schemas for inputs ingested from upstream stages.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


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


class ReviewTheme(BaseModel):
    """
    One evidence-backed theme consumed by SWOT Agent v7.

    Themes may combine customer voice from Google Maps, Facebook,
    and Instagram after normalization and theme extraction.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    theme_category: str

    entity_type: str = "target_business"

    frequency: int = Field(
        default=0,
        ge=0,
    )

    sentiment_balance: SentimentBalance = Field(
        default_factory=SentimentBalance,
    )

    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    target_score: Optional[float] = None

    competitor_score: Optional[float] = None

    performance_gap: Optional[float] = None

    mentions: List[Any] = Field(
        default_factory=list,
    )

    evidence_refs: List[Any] = Field(
        default_factory=list,
    )

    representative_quotes: List[str] = Field(
        default_factory=list,
    )

    source_platforms: List[str] = Field(
        default_factory=list,
    )


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