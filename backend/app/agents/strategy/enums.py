"""
Strategy Agent v1 - Enumerations
=================================
String-based enums for clean JSON serialization.
"""


class StrategyConfidence:
    """Confidence levels for strategies."""
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    EXPLORATORY = "exploratory"
    WATCHOUT = "watchout_only"


class StrategyHorizon:
    """Time horizons for strategy execution."""
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class StrategyType:
    """TOWS Matrix cell types."""
    SO = "SO"   # Strengths + Opportunities
    ST = "ST"   # Strengths + Threats
    WO = "WO"   # Weaknesses + Opportunities
    WT = "WT"   # Weaknesses + Threats


class StrategicPosture:
    """Overall strategic posture classifications."""
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


# Numeric ranking for confidence levels (higher = stronger)
CONFIDENCE_RANK = {
    StrategyConfidence.CONFIRMED: 4,
    StrategyConfidence.PROBABLE: 3,
    StrategyConfidence.EXPLORATORY: 2,
    StrategyConfidence.WATCHOUT: 1,
}