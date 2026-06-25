"""
SWOT Agent v7 - Configuration
=============================
All constants, thresholds, and tunable parameters.
"""

# ============================================================
# Engine Version
# ============================================================
ENGINE_VERSION = "7.0"


# ============================================================
# Theme Ingest Filters
# ============================================================
MIN_THEME_FREQUENCY = 2
MIN_SENTIMENT_TOTAL = 2


# ============================================================
# Sentiment Ratios
# ============================================================
POSITIVE_RATIO_STRENGTH = 0.70
NEGATIVE_RATIO_WEAKNESS = 0.35
SHADOW_MIN_NEGATIVE_MIX_RATIO = 0.15


# ============================================================
# Shadow Promotion Rules (FIX 2)
# ============================================================
SHADOW_PROMOTION_RULES = {
    "min_negative_ratio": 0.35,
    "min_negative_mentions": 3,
    "requires_manual_review": True,
}


# ============================================================
# Benchmark Thresholds (FIX 4)
# ============================================================
BENCHMARK_HIGH_MIN_REVIEWS_PER_COMPETITOR = 10
BENCHMARK_MEDIUM_MIN_COMPETITORS_AT_THRESHOLD = 2
RECOMMENDED_MIN_REVIEWS_PER_COMPETITOR = 10


# ============================================================
# Evidence Cap (FIX 3)
# ============================================================
EVIDENCE_DISPLAY_CAP = 10


# ============================================================
# Performance Score Clamps (FIX 5)
# ============================================================
WEAKNESS_MAX_PERFORMANCE = 4.5
STRENGTH_MIN_PERFORMANCE = 5.5
WEAKNESS_SCORING_ISSUE_FLOOR = 8.0
STRENGTH_SCORING_ISSUE_CEILING = 4.0


# ============================================================
# Strategic Priority Weights (Canonical)
# ============================================================
PRIORITY_WEIGHT_IMPORTANCE = 0.35
PRIORITY_WEIGHT_IMPACT = 0.25
PRIORITY_WEIGHT_CONFIDENCE = 0.20
PRIORITY_WEIGHT_FREQUENCY = 0.20


# ============================================================
# LLM Default Models
# ============================================================
DEFAULT_VERTEX_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


# ============================================================
# Retry Behaviour
# ============================================================
MAX_RETRIES_PER_PROVIDER = 3
RETRY_BACKOFF_BASE_SECONDS = 1.0  # 1, 2, 4


# ============================================================
# Cost Estimates (USD per call - rough heuristic)
# ============================================================
COST_ESTIMATE_USD = {
    "vertex_ai": 0.012,
    "anthropic": 0.025,
    "openai": 0.020,
    "groq": 0.001,
    "rule_based": 0.0,
}


# ============================================================
# Normalization
# ============================================================
FREQUENCY_NORMALIZATION_CEILING = 25  # mentions >= 25 -> score 10


# ============================================================
# Stop Tokens (for concept tokenization in FIX 8)
# ============================================================
STOP_TOKENS = {
    "the", "and", "with", "from", "this", "that", "have", "for", "into",
    "directional", "only", "benchmark", "available", "data", "more", "less",
    "based", "limited", "appears", "shows", "outperform", "competitor",
    "competitors", "review", "reviews", "early", "warning", "no", "clear",
    "critical", "risk", "growth", "opportunity", "advantage", "minor",
    "watchout", "confirmed", "concern", "concerns", "issue", "issues",
    "identified", "extend", "strength", "weakness", "threat", "directional)",
    "(directional", "insufficient", "evidence", "summarize", "to",
}