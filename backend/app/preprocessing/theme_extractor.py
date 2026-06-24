#!/usr/bin/env python3
"""
theme_extractor.py

Theme coding / theme extraction pipeline for cleaned, normalized business
intelligence datasets (output of a prior preprocessing/normalization step).

This script does NOT clean or normalize text, does NOT generate SWOT
analyses, and does NOT invent themes or evidence. It only analyzes the
already-cleaned `business_reviews` and `competitors[*].reviews_sample`
arrays to detect recurring themes, compare the target business against
competitors, and rank themes by strategic importance.

Usage:
    python theme_extractor.py input.json output.json
"""

import sys
import json
import re
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Predefined theme taxonomy
# ---------------------------------------------------------------------------
# Each predefined theme maps to:
#   - a human-readable display name
#   - a set of keyword/phrase patterns (lowercase, EN + AR) used to detect
#     the theme in review text and category_tags
#
# This taxonomy is intentionally conservative: it only matches explicit
# lexical signals already present in the text, so no themes are "invented".

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

# Order in which predefined themes are checked; also used as a tie-breaker
# for deterministic output ordering.
PREDEFINED_THEME_ORDER = list(PREDEFINED_THEMES.keys())

# Confidence weighting constants
MIN_MENTIONS_FOR_BASE_CONFIDENCE = 3
MAX_REPRESENTATIVE_QUOTES = 3


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_input(input_path: str) -> Dict[str, Any]:
    """Load and parse the cleaned/normalized JSON input file."""
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse input file '{input_path}' as JSON: {e}")
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object at the top level.")
    return data


def write_output(output_data: Dict[str, Any], output_path: str) -> None:
    """Write the resulting JSON output to disk."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Review collection helpers
# ---------------------------------------------------------------------------

def collect_all_reviews(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Gather all reviews (target business + competitors) into a single flat
    list, preserving their original fields. Each review dict is expected to
    already follow the unified schema produced by the normalization step:
        review_id, entity_name, entity_type, text, clean_text, rating,
        language, sentiment_hint, category_tags, is_synthetic,
        usable_for_analysis, source
    """
    all_reviews: List[Dict[str, Any]] = []

    business_reviews = data.get("business_reviews")
    if isinstance(business_reviews, list):
        all_reviews.extend(r for r in business_reviews if isinstance(r, dict))

    competitors = data.get("competitors")
    if isinstance(competitors, list):
        for comp in competitors:
            if not isinstance(comp, dict):
                continue
            samples = comp.get("reviews_sample")
            if isinstance(samples, list):
                all_reviews.extend(r for r in samples if isinstance(r, dict))

    return all_reviews


def get_review_text(review: Dict[str, Any]) -> str:
    """Return the cleaned text of a review, falling back to raw text."""
    text = review.get("clean_text")
    if not text:
        text = review.get("text")
    if not isinstance(text, str):
        return ""
    return text


def is_usable(review: Dict[str, Any]) -> bool:
    """
    A review is considered usable for theme extraction if it is marked
    usable_for_analysis (or that flag is missing/None, in which case we
    default to True), is not flagged synthetic, and has non-empty text.
    """
    if review.get("is_synthetic") is True:
        return False
    usable_flag = review.get("usable_for_analysis")
    if usable_flag is False:
        return False
    text = get_review_text(review)
    return bool(text and text.strip())


# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------

def build_keyword_pattern(keywords: List[str]) -> "re.Pattern":
    """
    Compile a case-insensitive regex pattern that matches any of the given
    keywords/phrases as whole words/phrases (where applicable).
    """
    escaped = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        # For ASCII keywords, use word boundaries; Arabic has no \b support
        # the same way, so match the phrase directly.
        if re.match(r'^[a-zA-Z0-9 \-]+$', kw):
            escaped.append(r'\b' + re.escape(kw) + r'\b')
        else:
            escaped.append(re.escape(kw))
    pattern = "|".join(escaped) if escaped else r'(?!x)x'  # never matches if empty
    return re.compile(pattern, flags=re.IGNORECASE | re.UNICODE)


PREDEFINED_PATTERNS: Dict[str, "re.Pattern"] = {
    theme_key: build_keyword_pattern(theme_info["keywords"])
    for theme_key, theme_info in PREDEFINED_THEMES.items()
}


def normalize_category_tag(tag: str) -> Optional[str]:
    """
    Map a free-form category_tag string to one of the predefined theme
    keys, if it directly corresponds to one (e.g. 'food_quality',
    'Food Quality', 'food-quality' -> 'food_quality').
    """
    if not isinstance(tag, str):
        return None
    norm = re.sub(r'[\s\-]+', '_', tag.strip().lower())
    if norm in PREDEFINED_THEMES:
        return norm
    return None


def detect_theme_categories_for_review(review: Dict[str, Any]) -> List[str]:
    """
    Detect which predefined theme categories apply to a single review,
    based on:
      1. Explicit category_tags that map directly to known theme keys.
      2. Keyword/phrase matches in the cleaned review text.

    Returns a list of unique theme category keys (predefined taxonomy).
    The list preserves PREDEFINED_THEME_ORDER for determinism.
    """
    matched: set = set()

    category_tags = review.get("category_tags")
    if isinstance(category_tags, list):
        for tag in category_tags:
            mapped = normalize_category_tag(tag)
            if mapped:
                matched.add(mapped)

    text = get_review_text(review)
    if text:
        for theme_key, pattern in PREDEFINED_PATTERNS.items():
            if pattern.search(text):
                matched.add(theme_key)

    return [t for t in PREDEFINED_THEME_ORDER if t in matched]


def discover_dynamic_themes(
    reviews: List[Dict[str, Any]],
    matched_theme_map: Dict[str, List[str]],
    min_frequency: int = 3,
) -> Dict[str, List[str]]:
    """
    Identify recurring patterns (frequent meaningful words/bigrams) in
    reviews that did NOT match any predefined theme, and group them into
    dynamically discovered "emerging" themes.

    `matched_theme_map` maps review_id -> list of predefined theme keys
    already matched for that review. Reviews with at least one predefined
    match are excluded from dynamic discovery to avoid double-counting.

    Returns a mapping of dynamic_theme_key -> list of review_ids that
    contain the corresponding recurring term.
    """
    # Lightweight stopword list (EN + common AR function words) to avoid
    # surfacing meaningless high-frequency tokens as "themes".
    stopwords = {
        "the", "and", "for", "are", "was", "were", "this", "that", "with",
        "from", "have", "has", "had", "but", "not", "you", "your", "they",
        "their", "its", "it's", "a", "an", "of", "in", "on", "to", "is",
        "be", "as", "at", "by", "or", "we", "i", "my", "our", "us",
        "very", "really", "just", "also", "so", "too", "more", "most",
        "place", "time", "here", "there",
        "في", "من", "على", "إلى", "عن", "هذا", "هذه", "كان", "كانت",
        "أن", "إن", "كل", "مع", "لا", "ما",
    }

    word_to_review_ids: Dict[str, set] = defaultdict(set)

    for review in reviews:
        review_id = review.get("review_id")
        if not review_id:
            continue
        if matched_theme_map.get(review_id):
            continue  # already covered by a predefined theme

        text = get_review_text(review)
        if not text:
            continue

        # Extract simple word tokens (Latin + Arabic ranges)
        tokens = re.findall(r'[A-Za-z\u0600-\u06FF]+', text.lower())
        for tok in tokens:
            if len(tok) < 4:
                continue
            if tok in stopwords:
                continue
            word_to_review_ids[tok].add(review_id)

    dynamic_themes: Dict[str, List[str]] = {}
    for word, review_ids in word_to_review_ids.items():
        if len(review_ids) >= min_frequency:
            theme_key = f"emerging_{word}"
            dynamic_themes[theme_key] = sorted(review_ids)

    return dynamic_themes


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_theme_data(
    reviews: List[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], Dict[str, List[str]]]:
    """
    For every (theme_category, entity_type) pair, aggregate:
      - mentions (review_ids)
      - sentiment_distribution
      - representative quotes
      - entity_names involved (for comparative signal computation)

    Also returns matched_theme_map: review_id -> list of predefined theme
    keys matched, for use in dynamic theme discovery.
    """
    aggregates: Dict[Tuple[str, str], Dict[str, Any]] = {}
    matched_theme_map: Dict[str, List[str]] = {}

    for review in reviews:
        if not is_usable(review):
            continue

        review_id = review.get("review_id", "")
        entity_type = review.get("entity_type", "unknown")
        entity_name = review.get("entity_name", "unknown")
        sentiment = review.get("sentiment_hint", "unknown")
        text = get_review_text(review)

        theme_keys = detect_theme_categories_for_review(review)
        matched_theme_map[review_id] = theme_keys

        for theme_key in theme_keys:
            agg_key = (theme_key, entity_type)
            if agg_key not in aggregates:
                aggregates[agg_key] = {
                    "mentions": [],
                    "sentiment_distribution": {
                        "positive": 0, "negative": 0,
                        "neutral": 0, "mixed": 0,
                    },
                    "quotes": [],
                    "entity_names": set(),
                }

            entry = aggregates[agg_key]
            entry["mentions"].append(review_id)
            entry["entity_names"].add(entity_name)

            if sentiment in entry["sentiment_distribution"]:
                entry["sentiment_distribution"][sentiment] += 1
            else:
                # 'unknown' or unexpected labels do not count toward any
                # of the four tracked buckets but the mention is preserved.
                pass

            if text and len(entry["quotes"]) < MAX_REPRESENTATIVE_QUOTES:
                entry["quotes"].append({
                    "review_id": review_id,
                    "entity_name": entity_name,
                    "text": text,
                    "sentiment": sentiment,
                })

    return aggregates, matched_theme_map


def aggregate_dynamic_theme_data(
    reviews: List[Dict[str, Any]],
    dynamic_themes: Dict[str, List[str]],
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Build aggregate entries for dynamically discovered themes, split by
    entity_type, mirroring the structure produced by aggregate_theme_data.
    """
    review_lookup = {r.get("review_id"): r for r in reviews if r.get("review_id")}
    aggregates: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for theme_key, review_ids in dynamic_themes.items():
        for review_id in review_ids:
            review = review_lookup.get(review_id)
            if not review or not is_usable(review):
                continue

            entity_type = review.get("entity_type", "unknown")
            entity_name = review.get("entity_name", "unknown")
            sentiment = review.get("sentiment_hint", "unknown")
            text = get_review_text(review)

            agg_key = (theme_key, entity_type)
            if agg_key not in aggregates:
                aggregates[agg_key] = {
                    "mentions": [],
                    "sentiment_distribution": {
                        "positive": 0, "negative": 0,
                        "neutral": 0, "mixed": 0,
                    },
                    "quotes": [],
                    "entity_names": set(),
                }

            entry = aggregates[agg_key]
            entry["mentions"].append(review_id)
            entry["entity_names"].add(entity_name)

            if sentiment in entry["sentiment_distribution"]:
                entry["sentiment_distribution"][sentiment] += 1

            if text and len(entry["quotes"]) < MAX_REPRESENTATIVE_QUOTES:
                entry["quotes"].append({
                    "review_id": review_id,
                    "entity_name": entity_name,
                    "text": text,
                    "sentiment": sentiment,
                })

    return aggregates


# ---------------------------------------------------------------------------
# Sentiment / signal helpers
# ---------------------------------------------------------------------------

def dominant_sentiment(distribution: Dict[str, int]) -> str:
    """
    Determine the dominant sentiment label for a theme aggregate.
    Returns one of: 'positive', 'negative', 'neutral', 'mixed'.

    A theme is considered 'mixed' if both positive and negative counts are
    present and neither overwhelmingly dominates (within a 1.5x ratio of
    each other), or if 'mixed' itself is the most common explicit label.
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)

    total = pos + neg + neu + mix
    if total == 0:
        return "unknown"

    if pos > 0 and neg > 0:
        ratio = (max(pos, neg) + 1) / (min(pos, neg) + 1)
        if ratio < 1.5 or mix > 0:
            return "mixed"

    counts = {"positive": pos, "negative": neg, "neutral": neu, "mixed": mix}
    return max(counts, key=lambda k: counts[k])


def compute_sentiment_intensity(distribution: Dict[str, int]) -> float:
    """
    Compute a 0.0-1.0 sentiment intensity score representing how strongly
    polarized (non-neutral) the theme's sentiment distribution is.
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)
    total = pos + neg + neu + mix
    if total == 0:
        return 0.0
    polarized = pos + neg + mix
    return round(polarized / total, 3)


# ---------------------------------------------------------------------------
# Theme record construction
# ---------------------------------------------------------------------------

def build_theme_record(
    theme_key: str,
    entity_type: str,
    entry: Dict[str, Any],
    is_predefined: bool,
) -> Dict[str, Any]:
    """
    Construct a single theme record (per theme_category + entity_type)
    following the required output schema (excluding comparative_signal,
    which is filled in later once cross-entity comparisons are available).
    """
    if is_predefined:
        display_name = PREDEFINED_THEMES[theme_key]["display_name"]
        theme_category = theme_key
    else:
        # theme_key looks like 'emerging_<word>'
        word = theme_key[len("emerging_"):]
        display_name = f"Emerging Theme: {word.capitalize()}"
        theme_category = theme_key

    mentions = entry["mentions"]
    frequency_count = len(mentions)
    sentiment_distribution = entry["sentiment_distribution"]

    quotes = [q["text"] for q in entry["quotes"]]

    confidence_score = compute_confidence_score(
        frequency_count, sentiment_distribution, is_predefined
    )

    return {
        "theme_name": display_name,
        "theme_category": theme_category,
        "entity_type": entity_type,
        "mentions": mentions,
        "frequency_count": frequency_count,
        "sentiment_distribution": dict(sentiment_distribution),
        "representative_quotes": quotes,
        "confidence_score": confidence_score,
        "comparative_signal": "not_applicable",
        "_entity_names": sorted(entry["entity_names"]),  # internal use only
    }


def compute_confidence_score(
    frequency_count: int,
    sentiment_distribution: Dict[str, int],
    is_predefined: bool,
) -> float:
    """
    Compute a confidence score (0.0-1.0) for a theme record based on:
      - number of supporting mentions (more mentions -> higher confidence)
      - whether the theme is from the predefined taxonomy (slightly higher
        baseline) vs. dynamically discovered (slightly lower baseline)
      - presence of 'unknown' sentiment entries (lowers confidence slightly)
    """
    base = 0.5 if is_predefined else 0.35

    if frequency_count >= MIN_MENTIONS_FOR_BASE_CONFIDENCE:
        freq_bonus = min(0.4, 0.1 * frequency_count)
    else:
        freq_bonus = 0.05 * frequency_count

    total_classified = sum(sentiment_distribution.values())
    unknown_penalty = 0.0
    if frequency_count > 0 and total_classified < frequency_count:
        unclassified = frequency_count - total_classified
        unknown_penalty = 0.05 * (unclassified / frequency_count)

    score = base + freq_bonus - unknown_penalty
    score = max(0.0, min(1.0, score))
    return round(score, 3)


# ---------------------------------------------------------------------------
# Comparative analysis
# ---------------------------------------------------------------------------

def compute_comparative_signals(
    theme_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For each theme_category present for both 'target_business' and
    'competitor' entity types, produce an additional 'comparative' theme
    record summarizing how the target business compares to competitors,
    and annotate each individual record's comparative_signal field.

    comparative_signal values:
      - 'overperforms': target sentiment notably more positive than competitors
      - 'underperforms': target sentiment notably more negative than competitors
      - 'parity': comparable sentiment between target and competitors
      - 'not_applicable': only one side has data for this theme
    """
    by_category: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for record in theme_records:
        by_category[record["theme_category"]][record["entity_type"]] = record

    comparative_records: List[Dict[str, Any]] = []

    for theme_category, entity_records in by_category.items():
        target = entity_records.get("target_business")
        competitor = entity_records.get("competitor")

        if target is None and competitor is None:
            continue

        if target is None or competitor is None:
            present = target or competitor
            present["comparative_signal"] = "not_applicable"
            continue

        target_score = sentiment_score(target["sentiment_distribution"])
        competitor_score = sentiment_score(competitor["sentiment_distribution"])

        diff = target_score - competitor_score

        if diff > 0.15:
            signal = "overperforms"
        elif diff < -0.15:
            signal = "underperforms"
        else:
            signal = "parity"

        target["comparative_signal"] = signal
        competitor["comparative_signal"] = signal

        combined_mentions = target["mentions"] + competitor["mentions"]
        combined_sentiment = combine_sentiment_distributions(
            target["sentiment_distribution"], competitor["sentiment_distribution"]
        )
        combined_quotes = (
            target["representative_quotes"][:2] +
            competitor["representative_quotes"][:2]
        )[:MAX_REPRESENTATIVE_QUOTES]

        comparative_record = {
            "theme_name": target["theme_name"],
            "theme_category": theme_category,
            "entity_type": "comparative",
            "mentions": combined_mentions,
            "frequency_count": len(combined_mentions),
            "sentiment_distribution": combined_sentiment,
            "representative_quotes": combined_quotes,
            "confidence_score": round(
                (target["confidence_score"] + competitor["confidence_score"]) / 2, 3
            ),
            "comparative_signal": signal,
            "_target_score": target_score,
            "_competitor_score": competitor_score,
        }
        comparative_records.append(comparative_record)

    return comparative_records


def sentiment_score(distribution: Dict[str, int]) -> float:
    """
    Compute a single scalar sentiment score in [-1.0, 1.0] from a
    sentiment distribution: +1 for positive, -1 for negative, 0 for
    neutral, and 0 contribution (but counted in total) for mixed.
    """
    pos = distribution.get("positive", 0)
    neg = distribution.get("negative", 0)
    neu = distribution.get("neutral", 0)
    mix = distribution.get("mixed", 0)
    total = pos + neg + neu + mix
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def combine_sentiment_distributions(
    a: Dict[str, int], b: Dict[str, int]
) -> Dict[str, int]:
    combined = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    for key in combined:
        combined[key] = a.get(key, 0) + b.get(key, 0)
    return combined


# ---------------------------------------------------------------------------
# Signal extraction (positive/negative/opportunity/threat)
# ---------------------------------------------------------------------------

def extract_signals(
    theme_records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Derive positive_signals, negative_signals, opportunity_signals, and
    threat_signals from theme records, based purely on observed sentiment
    distributions and comparative signals. No new information is invented;
    these are summaries of existing theme data.

    - positive_signals: target_business themes dominated by 'positive'
      sentiment.
    - negative_signals: target_business themes dominated by 'negative'
      sentiment.
    - opportunity_signals: comparative themes where target_business
      'overperforms' competitors.
    - threat_signals: comparative themes where target_business
      'underperforms' competitors, OR competitor-only themes with strong
      positive sentiment that the target business has no presence in.
    """
    positive_signals = []
    negative_signals = []
    opportunity_signals = []
    threat_signals = []

    for record in theme_records:
        entity_type = record["entity_type"]
        dist = record["sentiment_distribution"]
        dom = dominant_sentiment(dist)

        if entity_type == "target_business":
            if dom == "positive" and record["frequency_count"] > 0:
                positive_signals.append(_signal_summary(record, "positive_pattern"))
            elif dom == "negative" and record["frequency_count"] > 0:
                negative_signals.append(_signal_summary(record, "negative_pattern"))

        if entity_type == "comparative":
            if record["comparative_signal"] == "overperforms":
                opportunity_signals.append(_signal_summary(record, "overperforms_competitors"))
            elif record["comparative_signal"] == "underperforms":
                threat_signals.append(_signal_summary(record, "underperforms_competitors"))

        if entity_type == "competitor" and record["comparative_signal"] == "not_applicable":
            dom_comp = dominant_sentiment(dist)
            if dom_comp == "positive" and record["frequency_count"] >= MIN_MENTIONS_FOR_BASE_CONFIDENCE:
                threat_signals.append(_signal_summary(record, "competitor_strength_no_target_presence"))

    return positive_signals, negative_signals, opportunity_signals, threat_signals


def _signal_summary(record: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "theme_name": record["theme_name"],
        "theme_category": record["theme_category"],
        "entity_type": record["entity_type"],
        "reason": reason,
        "frequency_count": record["frequency_count"],
        "sentiment_distribution": record["sentiment_distribution"],
        "confidence_score": record["confidence_score"],
        "mentions": record["mentions"],
    }


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def compute_strategic_score(record: Dict[str, Any]) -> float:
    """
    Compute a strategic importance score for ranking themes.

    Factors:
      - frequency_count: more mentions -> higher importance
      - sentiment intensity: more polarized (positive or negative) themes
        are more strategically actionable than neutral ones
      - cross-entity spread: themes appearing for both target_business and
        competitors (i.e. 'comparative' records, or themes with a
        non-'not_applicable' comparative_signal) are prioritized
      - confidence_score: higher-confidence themes rank higher
    """
    frequency_count = record["frequency_count"]
    sentiment_intensity = compute_sentiment_intensity(record["sentiment_distribution"])
    confidence = record["confidence_score"]

    spread_bonus = 0.0
    if record["entity_type"] == "comparative":
        spread_bonus = 1.0
    elif record.get("comparative_signal") not in (None, "not_applicable"):
        spread_bonus = 0.5

    mixed_flag_bonus = 0.0
    if dominant_sentiment(record["sentiment_distribution"]) == "mixed":
        mixed_flag_bonus = 0.25

    score = (
        (frequency_count * 1.0)
        + (sentiment_intensity * 2.0)
        + (spread_bonus * 2.0)
        + (confidence * 1.5)
        + mixed_flag_bonus
    )
    return round(score, 4)


def rank_themes(theme_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort theme records by strategic_score (descending), with deterministic
    tie-breaking by theme_category order, entity_type, and theme_name.
    """
    def category_sort_key(category: str) -> int:
        if category in PREDEFINED_THEME_ORDER:
            return PREDEFINED_THEME_ORDER.index(category)
        return len(PREDEFINED_THEME_ORDER) + 1

    entity_type_order = {"comparative": 0, "target_business": 1, "competitor": 2}

    def sort_key(record: Dict[str, Any]):
        return (
            -record["_strategic_score"],
            category_sort_key(record["theme_category"]),
            entity_type_order.get(record["entity_type"], 99),
            record["theme_name"],
        )

    for record in theme_records:
        record["_strategic_score"] = compute_strategic_score(record)

    return sorted(theme_records, key=sort_key)


# ---------------------------------------------------------------------------
# Cleanup of internal fields
# ---------------------------------------------------------------------------

def strip_internal_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Remove internal-use-only keys (prefixed with '_') before output."""
    return {k: v for k, v in record.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def extract_themes(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main extraction pipeline: collect reviews, detect themes, aggregate,
    compute comparative signals, derive positive/negative/opportunity/
    threat signals, rank themes, and assemble the final output structure.
    """
    reviews = collect_all_reviews(data)

    aggregates, matched_theme_map = aggregate_theme_data(reviews)

    dynamic_themes = discover_dynamic_themes(reviews, matched_theme_map)
    dynamic_aggregates = aggregate_dynamic_theme_data(reviews, dynamic_themes)

    theme_records: List[Dict[str, Any]] = []

    for (theme_key, entity_type), entry in aggregates.items():
        theme_records.append(
            build_theme_record(theme_key, entity_type, entry, is_predefined=True)
        )

    emerging_theme_keys: set = set()
    for (theme_key, entity_type), entry in dynamic_aggregates.items():
        theme_records.append(
            build_theme_record(theme_key, entity_type, entry, is_predefined=False)
        )
        emerging_theme_keys.add(theme_key)

    comparative_records = compute_comparative_signals(theme_records)
    theme_records.extend(comparative_records)

    positive_signals, negative_signals, opportunity_signals, threat_signals = \
        extract_signals(theme_records)

    ranked_records = rank_themes(theme_records)

    top_themes = [
        {
            "theme_name": r["theme_name"],
            "theme_category": r["theme_category"],
            "entity_type": r["entity_type"],
            "strategic_score": r["_strategic_score"],
        }
        for r in ranked_records[:10]
    ]

    emerging_themes = [
        {
            "theme_name": r["theme_name"],
            "theme_category": r["theme_category"],
            "entity_type": r["entity_type"],
            "frequency_count": r["frequency_count"],
            "confidence_score": r["confidence_score"],
        }
        for r in ranked_records
        if r["theme_category"] in emerging_theme_keys
    ]

    comparison_summary = build_comparison_summary(comparative_records)

    final_records = [strip_internal_fields(r) for r in ranked_records]

    output = {
        "themes": final_records,
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "opportunity_signals": opportunity_signals,
        "threat_signals": threat_signals,
        "top_themes": top_themes,
        "emerging_themes": emerging_themes,
        "comparison_summary": comparison_summary,
    }

    return output


def build_comparison_summary(
    comparative_records: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Build the comparison_summary section listing theme categories where the
    target business overperforms, underperforms, or is at parity with
    competitors.
    """
    overperforms: List[str] = []
    underperforms: List[str] = []
    parity: List[str] = []

    for record in comparative_records:
        category = record["theme_category"]
        signal = record["comparative_signal"]
        if signal == "overperforms":
            overperforms.append(category)
        elif signal == "underperforms":
            underperforms.append(category)
        elif signal == "parity":
            parity.append(category)

    return {
        "target_business_overperforms": overperforms,
        "target_business_underperforms": underperforms,
        "parity_areas": parity,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def extract_themes_from_normalized(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes normalized data (the output of normalize.normalize_raw_data) and
    returns the theme-analysis dict.

    This is a thin, intention-revealing alias over :func:`extract_themes`,
    provided so the SWOT pipeline orchestrator can chain stages with a
    consistent public API. The input must already be normalized (i.e. contain
    `business_reviews` and/or `competitors[*].reviews_sample`).
    """
    return extract_themes(normalized_data)


def main() -> None:
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: python theme_extractor.py input.json output.json\n")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    try:
        data = load_input(input_path)
    except FileNotFoundError:
        sys.stderr.write(f"Error: input file not found: {input_path}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    try:
        output_data = extract_themes(data)
    except Exception as e:
        sys.stderr.write(f"Error during theme extraction: {e}\n")
        sys.exit(1)

    try:
        write_output(output_data, output_path)
    except OSError as e:
        sys.stderr.write(f"Error writing output file: {e}\n")
        sys.exit(1)

    sys.stdout.write(f"Theme extraction complete. Output written to: {output_path}\n")


if __name__ == "__main__":
    main()
