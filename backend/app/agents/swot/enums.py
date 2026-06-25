"""
SWOT Agent v7 - Enumerations
============================
All enums used across the SWOT pipeline.
"""
from enum import Enum


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
    """SWOT quadrants."""
    STRENGTHS = "strengths"
    WEAKNESSES = "weaknesses"
    OPPORTUNITIES = "opportunities"
    THREATS = "threats"