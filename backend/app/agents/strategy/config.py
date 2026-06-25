"""
Strategy Agent v1 - Configuration
==================================
All constants and tunable parameters.
"""


# ============================================================
# Engine Version
# ============================================================
ENGINE_VERSION = "1.0"


# ============================================================
# Max Strategies per TOWS Cell
# ============================================================
MAX_SO_STRATEGIES = 3
MAX_ST_STRATEGIES = 2
MAX_WO_STRATEGIES = 2
MAX_WT_STRATEGIES = 2


# ============================================================
# Output Limits
# ============================================================
MAX_PRIORITY_ACTIONS = 8
MAX_CAMPAIGN_FEED_ITEMS = 5


# ============================================================
# Confidence Weights for Urgency Ranking
# ============================================================
CONFIDENCE_WEIGHTS = {
    "confirmed": 1.0,
    "probable": 0.8,
    "exploratory": 0.5,
    "watchout_only": 0.2,
}


# ============================================================
# Effort & Impact Weights
# ============================================================
EFFORT_WEIGHTS = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

IMPACT_WEIGHTS = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


# ============================================================
# Thresholds
# ============================================================
# Vulnerability threshold that forces immediate horizon for ST strategies
VULNERABILITY_IMMEDIATE_THRESHOLD = 6.0

# Strategic-priority threshold that flips LEVERAGE_LED posture on
LEVERAGE_PRIORITY_FLOOR = 8.0