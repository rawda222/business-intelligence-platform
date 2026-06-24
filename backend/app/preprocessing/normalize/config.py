"""
Normalize Configuration
======================
All constants, regex patterns, and word lists used by the normalize pipeline.

This module has NO dependencies on other normalize submodules.
"""
import re


# ---------------------------------------------------------------------------
# Language detection ranges
# ---------------------------------------------------------------------------
ARABIC_RANGE = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)
LATIN_RANGE = re.compile(r'[A-Za-z]')


# ---------------------------------------------------------------------------
# Emoji ranges
# ---------------------------------------------------------------------------
# Emojis that typically carry sentiment (faces, hearts, hand gestures,
# food, common symbols). Used to decide which emojis are "meaningful".
SENTIMENT_EMOJI_RANGE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs (subset incl. food/hearts)
    "\U0001F680-\U0001F6FF"  # transport
    "\U00002700-\U000027BF"  # dingbats (includes some hearts/checks)
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)

# Other emoji / symbol ranges considered "non-sentiment noise"
# (e.g. flags, decorative symbols, variation selectors) -- these get stripped.
NON_SENTIMENT_SYMBOL_RANGE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # regional indicator symbols (flags)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0001F000-\U0001F0FF"  # mahjong/dominoes/playing cards
    "]+",
    flags=re.UNICODE,
)


# ---------------------------------------------------------------------------
# Sentiment word lists (English)
# ---------------------------------------------------------------------------
POSITIVE_WORDS_EN = {
    "good", "great", "excellent", "amazing", "love", "loved", "best",
    "perfect", "delicious", "friendly", "wonderful", "nice", "fresh",
    "recommend", "awesome", "fantastic", "clean", "comfortable", "calm",
    "elegant", "tasty", "favorite", "favourite", "enjoy", "enjoyed",
}

NEGATIVE_WORDS_EN = {
    "bad", "worst", "terrible", "awful", "slow", "rude", "dirty",
    "expensive", "overpriced", "disappointing", "disappointed", "poor",
    "cold", "stale", "horrible", "never", "complaint", "complain",
    "waited", "waiting", "wait", "noisy", "small",
}


# ---------------------------------------------------------------------------
# Sentiment word lists (Arabic)
# ---------------------------------------------------------------------------
POSITIVE_WORDS_AR = {
    "جميل", "ممتاز", "رائع", "لذيذ", "نظيف", "احب", "أحب", "افضل",
    "أفضل", "مريح", "هادئ", "جيد", "رائعة", "جميلة", "نظيفة", "مميز",
}

NEGATIVE_WORDS_AR = {
    "سيء", "سيئ", "بطيء", "غالي", "وسخ", "مزعج", "سيئة", "ردئ",
    "رديء", "بطيئة", "مقرف", "ضعيف", "مخيب",
}


# ---------------------------------------------------------------------------
# Synthetic / placeholder markers
# ---------------------------------------------------------------------------
SYNTHETIC_MARKERS = [
    "lorem ipsum",
    "test review",
    "sample review",
    "placeholder",
    "n/a",
    "todo",
    "tbd",
    "this is a test",
    "example text",
    "xxx",
    "sample text",
]


# ---------------------------------------------------------------------------
# Duplicate detection threshold
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD = 0.85