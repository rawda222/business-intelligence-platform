"""
Theme Taxonomy
==============
Predefined theme categories with keyword patterns (EN + AR).

Each theme maps to:
- display_name: human-readable label
- keywords: list of keywords/phrases to detect the theme
"""
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Predefined themes
# ---------------------------------------------------------------------------
PREDEFINED_THEMES: Dict[str, Dict[str, Any]] = {
    "food_quality": {
        "display_name": "Food Quality",
        "keywords": [
            "food quality", "taste", "tasty", "delicious", "fresh",
            "freshness", "flavor", "flavour", "ingredients", "meal",
            "dish", "cuisine", "recipe",
            "طعم", "لذيذ", "طازج", "جودة الطعام", "أكل",
        ],
    },
    "coffee_quality": {
        "display_name": "Coffee Quality",
        "keywords": [
            "coffee", "espresso", "latte", "cappuccino", "brew",
            "roast", "barista",
            "قهوة", "اسبريسو", "كابتشينو",
        ],
    },
    "service": {
        "display_name": "Service",
        "keywords": [
            "service", "staff", "waiter", "waitress", "server",
            "professional", "attentive",
            "خدمة", "موظف", "نادل",
        ],
    },
    "service_speed": {
        "display_name": "Service Speed",
        "keywords": [
            "slow", "fast", "quick", "wait", "waited", "waiting",
            "delay", "delayed", "took forever", "speed", "service speed",
            "بطيء", "سريع", "انتظار",
        ],
    },
    "ambience": {
        "display_name": "Ambience",
        "keywords": [
            "ambience", "ambiance", "atmosphere", "vibe", "decor",
            "interior", "calm", "cozy", "elegant", "music", "lighting",
            "أجواء", "ديكور", "هادئ",
        ],
    },
    "cleanliness": {
        "display_name": "Cleanliness",
        "keywords": [
            "clean", "cleanliness", "dirty", "hygiene", "spotless",
            "messy", "stain",
            "نظيف", "نظافة", "وسخ",
        ],
    },
    "pricing": {
        "display_name": "Pricing",
        "keywords": [
            "price", "pricing", "expensive", "cheap", "cost", "costly",
            "overpriced", "affordable",
            "سعر", "غالي", "رخيص",
        ],
    },
    "value_perception": {
        "display_name": "Value Perception",
        "keywords": [
            "value", "worth it", "worth the", "value for money",
            "bang for your buck", "rip off", "ripoff",
            "يستاهل", "يستحق",
        ],
    },
    "menu_variety": {
        "display_name": "Menu Variety",
        "keywords": [
            "menu", "variety", "options", "selection", "choices",
            "limited menu",
            "قائمة", "تنوع", "خيارات",
        ],
    },
    "location": {
        "display_name": "Location",
        "keywords": [
            "location", "located", "easy to find", "parking",
            "accessible", "neighborhood", "neighbourhood",
            "موقع", "مكان", "موقف سيارات",
        ],
    },
    "customer_experience": {
        "display_name": "Customer Experience",
        "keywords": [
            "experience", "overall experience", "visit", "recommend",
            "would recommend", "enjoyed", "enjoy",
            "تجربة", "ننصح",
        ],
    },
    "staff_behavior": {
        "display_name": "Staff Behavior",
        "keywords": [
            "friendly", "rude", "polite", "helpful", "welcoming",
            "attitude", "courteous", "unfriendly",
            "ودود", "وقح", "لطيف",
        ],
    },
    "crowding": {
        "display_name": "Crowding",
        "keywords": [
            "crowded", "busy", "packed", "full", "no seats",
            "long line", "queue",
            "مزدحم", "زحمة", "طابور",
        ],
    },
    "brand_image": {
        "display_name": "Brand Image",
        "keywords": [
            "brand", "reputation", "well known", "popular", "famous",
            "image",
            "علامة تجارية", "سمعة", "مشهور",
        ],
    },
    "convenience": {
        "display_name": "Convenience",
        "keywords": [
            "convenient", "convenience", "easy", "accessible",
            "delivery", "takeaway", "take away", "drive thru",
            "drive-thru", "online order",
            "سهل", "توصيل", "استلام",
        ],
    },
}


# Theme order for deterministic output
PREDEFINED_THEME_ORDER = list(PREDEFINED_THEMES.keys())


# ---------------------------------------------------------------------------
# Compile keyword patterns
# ---------------------------------------------------------------------------
def build_keyword_pattern(keywords: List[str]) -> re.Pattern:
    """
    Compile a case-insensitive regex pattern matching any keyword.
    
    For ASCII keywords, uses word boundaries.
    For Arabic, uses substring matching (no word boundary support).
    """
    escaped = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        if re.match(r'^[a-zA-Z0-9 -]+$', kw):
            escaped.append(r'\b' + re.escape(kw) + r'\b')
        else:
            escaped.append(re.escape(kw))
    
    pattern = "|".join(escaped) if escaped else r'(?!x)x'
    return re.compile(pattern, flags=re.IGNORECASE | re.UNICODE)


# Precompiled patterns for all predefined themes
PREDEFINED_PATTERNS: Dict[str, re.Pattern] = {
    theme_key: build_keyword_pattern(theme_info["keywords"])
    for theme_key, theme_info in PREDEFINED_THEMES.items()
}


# ---------------------------------------------------------------------------
# Category tag normalization
# ---------------------------------------------------------------------------
def normalize_category_tag(tag: str) -> Optional[str]:
    """
    Map a free-form category tag to a predefined theme key.
    
    Examples:
        'food_quality' -> 'food_quality'
        'Food Quality' -> 'food_quality'
        'food-quality' -> 'food_quality'
        'unknown' -> None
    """
    if not isinstance(tag, str):
        return None
    
    norm = re.sub(r'[\s-]+', '_', tag.strip().lower())
    if norm in PREDEFINED_THEMES:
        return norm
    
    return None