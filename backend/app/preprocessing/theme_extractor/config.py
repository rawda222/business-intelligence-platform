"""
Theme Extractor Configuration
=============================
Constants and thresholds for theme extraction.
"""


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------
MIN_MENTIONS_FOR_BASE_CONFIDENCE = 3
MAX_REPRESENTATIVE_QUOTES = 3


# ---------------------------------------------------------------------------
# Dynamic theme discovery
# ---------------------------------------------------------------------------
MIN_FREQUENCY_FOR_DYNAMIC_THEME = 3


# ---------------------------------------------------------------------------
# Signal classification thresholds
# ---------------------------------------------------------------------------
POSITIVE_SIGNAL_RATIO = 0.70
NEGATIVE_SIGNAL_RATIO = 0.35


# ---------------------------------------------------------------------------
# Comparative analysis thresholds
# ---------------------------------------------------------------------------
COMPARATIVE_GAP_THRESHOLD = 0.15  # 15% diff to be "over/underperform"