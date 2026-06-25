"""
SWOT Agent v7 - Production-Grade Modular Package
=================================================

Public API:
    from app.agents.swot import SWOTAgent
    from app.agents.swot.schemas.input import BusinessProfile, ReviewTheme
    from app.agents.swot.schemas.output import SWOTOutput
    from app.agents.swot.enums import LLMProvider

Usage:
    agent = SWOTAgent(provider=LLMProvider.VERTEX_AI)
    output = agent.run(business_profile)
    print(output.model_dump_json(indent=2))
"""
from app.agents.swot.pipeline import SWOTAgent
from app.agents.swot.enums import LLMProvider, ClaimStrength, Quadrant
from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
    CompetitorProfile,
    ReviewsSummary,
)
from app.agents.swot.schemas.output import SWOTOutput, SWOTReport

__all__ = [
    "SWOTAgent",
    "LLMProvider",
    "ClaimStrength",
    "Quadrant",
    "BusinessProfile",
    "ReviewTheme",
    "SentimentBalance",
    "CompetitorProfile",
    "ReviewsSummary",
    "SWOTOutput",
    "SWOTReport",
]