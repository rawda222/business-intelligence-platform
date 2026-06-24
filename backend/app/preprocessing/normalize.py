#!/usr/bin/env python3
"""
normalize.py

Production-ready data cleaning, preprocessing, and normalization script
for messy, mixed-format business intelligence datasets (e.g. scraped
business profiles, reviews, and competitor data).

Usage:
    python normalize.py input.json output.json
"""

import sys
import json
import re
import hashlib
import unicodedata
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARABIC_RANGE = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)
LATIN_RANGE = re.compile(r'[A-Za-z]')

# Emoji ranges that typically carry sentiment (faces, hearts, hand gestures,
# food, common symbols). Used to decide which emojis are "meaningful".
SENTIMENT_EMOJI_RANGE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs (subset incl. food/hearts)
    "\U0001F680-\U0001F6FF"  # transport (rarely sentiment, kept conservative)
    "\U00002700-\U000027BF"  # dingbats (includes some hearts/checks)
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)

# Other emoji / symbol ranges considered "non-sentiment noise" (e.g. flags,
# decorative symbols, variation selectors) -- these get stripped.
NON_SENTIMENT_SYMBOL_RANGE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # regional indicator symbols (flags)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0001F000-\U0001F0FF"  # mahjong/dominoes/playing cards
    "]+",
    flags=re.UNICODE,
)

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

POSITIVE_WORDS_AR = {
    "جميل", "ممتاز", "رائع", "لذيذ", "نظيف", "احب", "أحب", "افضل",
    "أفضل", "مريح", "هادئ", "جيد", "رائعة", "جميلة", "نظيفة", "مميز",
}
NEGATIVE_WORDS_AR = {
    "سيء", "سيئ", "بطيء", "غالي", "وسخ", "مزعج", "سيئة", "ردئ",
    "رديء", "بطيئة", "مقرف", "ضعيف", "مخيب",
}

# Common placeholder / synthetic markers
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
# Generic helpers
# ---------------------------------------------------------------------------

def safe_get(d, keys, default=None):
    """
    Defensive lookup across multiple possible key names.
    `keys` can be a string or a list/tuple of candidate key names.
    Returns `default` if none of the keys are present or value is falsy-empty
    (but 0 / False are preserved).
    """
    if d is None or not isinstance(d, dict):
        return default

    if isinstance(keys, str):
        keys = [keys]

    for k in keys:
        if k in d and d[k] is not None:
            return d[k]

    # Case-insensitive fallback
    lower_map = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        lk = str(k).lower()
        if lk in lower_map and lower_map[lk] is not None:
            return lower_map[lk]

    return default


def extract_text_value(value):
    """
    Some source records store review text as a dict keyed by language code,
    e.g. {'ar': '...'} or {'en': '...', 'ar': '...'}, sometimes serialized
    as a Python-repr string like "{'ar': '...'}" rather than valid JSON.
    This helper unwraps such structures and returns the underlying text
    string (preferring 'ar', then 'en', then any other value), without
    altering the actual review content.
    """
    if value is None:
        return None

    # Already a plain string
    if isinstance(value, str):
        stripped = value.strip()
        # Detect a Python-repr-style dict string, e.g. "{'ar': '...'}"
        if stripped.startswith("{") and stripped.endswith("}") and (
            "'ar'" in stripped or '"ar"' in stripped
            or "'en'" in stripped or '"en"' in stripped
        ):
            try:
                import ast
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, dict):
                    return extract_text_value(parsed)
            except (ValueError, SyntaxError):
                pass
        return value

    # Actual dict (already-parsed JSON), e.g. {'ar': '...', 'en': '...'}
    if isinstance(value, dict):
        for lang_key in ("ar", "en", "mixed"):
            if lang_key in value and isinstance(value[lang_key], str):
                return value[lang_key]
        # Fall back to first string value found
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v
        return None

    return value


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def to_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        s = re.sub(r'[^\d\.\-]', '', s)
        if s in ("", "-", "."):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def to_int(value):
    f = to_float(value)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def strip_non_sentiment_symbols(text):
    return NON_SENTIMENT_SYMBOL_RANGE.sub("", text)


def normalize_repeated_punctuation(text):
    """
    Collapse repeated punctuation (e.g. '!!!!' -> '!', '??' -> '?',
    '.....' -> '...') while preserving meaningful emphasis (cap at one
    repetition for '!' and '?', cap '.' at three for ellipsis).
    """
    # Collapse 4+ dots/periods to an ellipsis '...'
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'\.{2,3}', '...', text)

    # Collapse repeated '!' to a single '!'
    text = re.sub(r'!{2,}', '!', text)

    # Collapse repeated '?' to a single '?'
    text = re.sub(r'\?{2,}', '?', text)

    # Collapse repeated commas
    text = re.sub(r',{2,}', ',', text)

    # Collapse repeated dashes / underscores
    text = re.sub(r'-{3,}', '--', text)
    text = re.sub(r'_{3,}', '__', text)

    return text


def normalize_whitespace(text):
    # Normalize unicode (combine accents, etc.) without altering meaning
    text = unicodedata.normalize("NFC", text)

    # Replace non-breaking spaces and similar with normal space
    text = re.sub(r'[\u00A0\u200B\u200C\u200D\uFEFF]', ' ', text)

    # Collapse multiple spaces/tabs into a single space
    text = re.sub(r'[ \t]+', ' ', text)

    # Collapse 3+ line breaks (with possible whitespace between) into a
    # single line break
    text = re.sub(r'(\r\n|\r|\n)\s*(\r\n|\r|\n)+', '\n', text)

    # Trim trailing whitespace on each line
    text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()


def clean_text(raw_text):
    """
    Main text-cleaning pipeline:
      - normalize whitespace / line breaks
      - normalize repeated punctuation
      - remove non-sentiment-bearing symbols (flags, variation selectors)
      - preserve language and meaningful (sentiment) emojis
      - never alters wording / meaning of the actual content
    """
    if raw_text is None:
        return None

    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    text = raw_text
    text = strip_non_sentiment_symbols(text)
    text = normalize_repeated_punctuation(text)
    text = normalize_whitespace(text)

    return text


# ---------------------------------------------------------------------------
# Language & sentiment detection
# ---------------------------------------------------------------------------

def detect_language(text):
    if not text or not isinstance(text, str) or text.strip() == "":
        return "unknown"

    has_arabic = bool(ARABIC_RANGE.search(text))
    has_latin = bool(LATIN_RANGE.search(text))

    if has_arabic and has_latin:
        return "mixed"
    if has_arabic:
        return "ar"
    if has_latin:
        return "en"
    return "unknown"


def detect_sentiment_hint(text, rating=None, predefined_sentiment=None):
    """
    Lightweight, heuristic sentiment detection.
    Priority:
      1. If a predefined sentiment label exists in the source data, use it
         (normalized).
      2. Otherwise, derive from rating if available.
      3. Otherwise, derive from keyword matching (EN + AR).
      4. Fallback to 'unknown'.
    """
    # 1. Predefined sentiment from source
    if predefined_sentiment and isinstance(predefined_sentiment, str):
        norm = predefined_sentiment.strip().lower()
        mapping = {
            "positive": "positive",
            "pos": "positive",
            "negative": "negative",
            "neg": "negative",
            "neutral": "neutral",
            "mixed": "mixed",
            "unknown": "unknown",
        }
        if norm in mapping:
            return mapping[norm]

    text_lower = (text or "").lower()
    found_pos = any(w in text_lower for w in POSITIVE_WORDS_EN)
    found_neg = any(w in text_lower for w in NEGATIVE_WORDS_EN)

    found_pos_ar = any(w in (text or "") for w in POSITIVE_WORDS_AR)
    found_neg_ar = any(w in (text or "") for w in NEGATIVE_WORDS_AR)

    found_pos = found_pos or found_pos_ar
    found_neg = found_neg or found_neg_ar

    keyword_sentiment = None
    if found_pos and found_neg:
        keyword_sentiment = "mixed"
    elif found_pos:
        keyword_sentiment = "positive"
    elif found_neg:
        keyword_sentiment = "negative"

    # 2. Rating-based sentiment
    rating_sentiment = None
    r = to_float(rating)
    if r is not None:
        if r >= 4.0:
            rating_sentiment = "positive"
        elif r <= 2.0:
            rating_sentiment = "negative"
        else:
            rating_sentiment = "neutral"

    # Combine rating + keyword signals
    if keyword_sentiment and rating_sentiment:
        if keyword_sentiment == rating_sentiment:
            return keyword_sentiment
        if "mixed" in (keyword_sentiment, rating_sentiment):
            return "mixed"
        # Conflicting clear signals
        return "mixed"

    if keyword_sentiment:
        return keyword_sentiment
    if rating_sentiment:
        return rating_sentiment

    if not text or text.strip() == "":
        return "unknown"

    return "neutral"


# ---------------------------------------------------------------------------
# Synthetic / placeholder detection
# ---------------------------------------------------------------------------

def is_synthetic_text(text, source_flag=None):
    """
    Returns True if the text appears to be a placeholder, synthetic,
    or auto-generated sample rather than a real review.
    """
    if source_flag is True:
        return True

    if not text or not isinstance(text, str):
        return False

    t = text.strip().lower()

    if t == "":
        return True

    for marker in SYNTHETIC_MARKERS:
        if marker in t:
            return True

    # Very short generic strings with no real content
    if len(t) <= 3 and t.isascii():
        return True

    return False


# ---------------------------------------------------------------------------
# Hashing / duplicate detection
# ---------------------------------------------------------------------------

def normalize_for_hash(text):
    """Aggressively normalize text purely for duplicate-detection hashing."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[^\w\u0600-\u06FF]+', ' ', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def text_hash(text):
    norm = normalize_for_hash(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def text_similarity(a, b):
    """
    Simple Jaccard similarity over word sets. Used as a lightweight,
    dependency-free near-duplicate detector.
    """
    set_a = set(normalize_for_hash(a).split())
    set_b = set(normalize_for_hash(b).split())
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


SIMILARITY_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Review normalization
# ---------------------------------------------------------------------------

def build_review_id(entity_type, entity_name, index, raw_text):
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', (entity_name or "unknown")).strip("_").lower()
    if not safe_name:
        safe_name = "unknown"
    h = hashlib.sha1((raw_text or "").encode("utf-8")).hexdigest()[:8]
    return f"{entity_type}_{safe_name}_{index}_{h}"


def normalize_review(raw_review, entity_name, entity_type, index, source,
                      quality_report):
    """
    Convert a raw review dict (with arbitrary/inconsistent keys) into the
    unified review schema.
    """
    if not isinstance(raw_review, dict):
        # Handle case where review is just a raw string
        raw_review = {"text": raw_review}

    raw_text = safe_get(raw_review, ["text", "review_text", "content",
                                      "comment", "body", "message"])

    raw_text = extract_text_value(raw_text)

    if raw_text is not None and not isinstance(raw_text, str):
        raw_text = str(raw_text)

    cleaned = clean_text(raw_text) if raw_text is not None else None

    rating = safe_get(raw_review, ["rating", "score", "stars"])
    rating = to_float(rating)

    predefined_sentiment = safe_get(
        raw_review, ["sentiment", "sentiment_hint", "sentiment_label"]
    )

    category_tags = safe_get(
        raw_review, ["category_tags", "category", "categories", "tags"]
    )
    if category_tags is None:
        category_tags = []
    elif isinstance(category_tags, str):
        category_tags = [category_tags]
    elif not isinstance(category_tags, list):
        category_tags = [str(category_tags)]

    is_synth_flag = safe_get(raw_review, ["is_synthetic", "synthetic", "is_sample"])
    is_synthetic = is_synthetic_text(cleaned, source_flag=is_synth_flag)

    language = detect_language(cleaned)
    sentiment_hint = detect_sentiment_hint(cleaned, rating, predefined_sentiment)

    review_id = safe_get(raw_review, ["review_id", "id"])
    if not review_id:
        review_id = build_review_id(entity_type, entity_name, index, raw_text or "")

    missing_fields = []
    if is_empty(raw_text):
        missing_fields.append("text")
    if rating is None:
        missing_fields.append("rating")

    usable_for_analysis = True
    reasons = []

    if is_empty(cleaned):
        usable_for_analysis = False
        reasons.append("empty_text")

    if is_synthetic:
        usable_for_analysis = False
        reasons.append("synthetic_or_placeholder")

    if cleaned and len(cleaned.strip()) < 5:
        usable_for_analysis = False
        reasons.append("too_short")

    normalized = {
        "review_id": review_id,
        "entity_name": entity_name if entity_name else "unknown",
        "entity_type": entity_type,
        "text": raw_text if raw_text is not None else None,
        "clean_text": cleaned,
        "rating": rating,
        "language": language,
        "sentiment_hint": sentiment_hint,
        "category_tags": category_tags,
        "is_synthetic": bool(is_synthetic),
        "usable_for_analysis": usable_for_analysis,
        "source": source if source else "unknown",
    }

    if missing_fields:
        quality_report["missing_fields"].append({
            "review_id": review_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "missing": missing_fields,
        })

    if not usable_for_analysis:
        quality_report["manual_review_needed"].append({
            "review_id": review_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "reasons": reasons,
        })

    if is_synthetic:
        quality_report["synthetic_items"].append({
            "review_id": review_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "text_preview": (cleaned or "")[:120],
        })

    return normalized


def normalize_reviews_collection(raw_reviews, entity_name, entity_type,
                                  source, quality_report):
    """
    raw_reviews may be:
      - a list of review dicts/strings
      - a dict containing a list under common keys (e.g. 'items', 'list',
        'reviews', 'reviews_sample')
      - None / missing
    Returns a list of normalized review dicts.
    """
    if raw_reviews is None:
        return []

    if isinstance(raw_reviews, dict):
        for key in ["items", "list", "reviews", "reviews_sample", "data",
                     "samples", "raw_samples"]:
            if key in raw_reviews and isinstance(raw_reviews[key], list):
                raw_reviews = raw_reviews[key]
                break
        else:
            # Treat dict-of-reviews (keyed by id) as a list of values
            if all(isinstance(v, dict) for v in raw_reviews.values()):
                raw_reviews = list(raw_reviews.values())
            else:
                raw_reviews = []

    if not isinstance(raw_reviews, list):
        return []

    normalized_list = []
    for idx, raw_review in enumerate(raw_reviews):
        normalized_list.append(
            normalize_review(raw_review, entity_name, entity_type, idx,
                              source, quality_report)
        )
    return normalized_list


# ---------------------------------------------------------------------------
# Business profile normalization
# ---------------------------------------------------------------------------

def normalize_business_profile(raw_data, quality_report):
    identity = safe_get(raw_data, ["business_identity", "identity", "profile"]) or {}
    contact = safe_get(raw_data, ["contact_presence", "contact"]) or {}
    commercial = safe_get(raw_data, ["commercial"]) or {}
    pricing = safe_get(commercial, ["pricing"]) or {}
    visual_identity = safe_get(raw_data, ["visual_identity"]) or {}
    brand_voice = safe_get(raw_data, ["brand_voice"]) or {}
    marketing_signals = safe_get(raw_data, ["marketing_signals"]) or {}
    offerings = safe_get(raw_data, ["offerings"]) or []

    profile_fields = {
        "business_name": safe_get(identity, ["business_name", "name"]),
        "category": safe_get(identity, ["category"]),
        "subcategory": safe_get(identity, ["subcategory"]),
        "description": clean_text(safe_get(identity, ["description"])),
        "source_url": safe_get(identity, ["source_url", "url"]),
        "final_url": safe_get(identity, ["final_url", "website"]),
        "address": safe_get(raw_data, ["address", "location"]),
        "contact_presence": contact if isinstance(contact, dict) else {},
        "pricing": {
            "billing_model": safe_get(pricing, ["billing_model"]),
            "posture": safe_get(pricing, ["posture"]),
            "price_range": safe_get(pricing, ["price_range"]),
            "visible": safe_get(pricing, ["visible"]),
        },
        "visual_identity": visual_identity if isinstance(visual_identity, dict) else {},
        "brand_voice": brand_voice if isinstance(brand_voice, dict) else {},
        "marketing_signals": marketing_signals if isinstance(marketing_signals, dict) else {},
        "offerings": offerings if isinstance(offerings, list) else [],
    }

    # Track missing top-level identity fields
    for field in ["business_name", "category", "description", "source_url"]:
        if is_empty(profile_fields.get(field)):
            quality_report["missing_fields"].append({
                "section": "business_profile",
                "field": field,
            })
            profile_fields[field] = profile_fields.get(field) if profile_fields.get(field) is not None else "unknown"

    return profile_fields


# ---------------------------------------------------------------------------
# Competitor normalization
# ---------------------------------------------------------------------------

def normalize_competitor(raw_competitor, index, quality_report):
    if not isinstance(raw_competitor, dict):
        quality_report["mismatches"].append({
            "section": "competitors",
            "index": index,
            "issue": "competitor entry is not an object",
        })
        return None

    name = safe_get(raw_competitor, ["name", "business_name"])
    if is_empty(name):
        quality_report["missing_fields"].append({
            "section": "competitors",
            "index": index,
            "field": "name",
        })
        name = "unknown"

    rating = to_float(safe_get(raw_competitor, ["rating", "score"]))
    review_count = to_int(safe_get(raw_competitor, ["review_count", "reviews_count", "num_reviews"]))
    address = safe_get(raw_competitor, ["address", "location"])
    positioning = safe_get(raw_competitor, ["positioning"])
    price_level = safe_get(raw_competitor, ["price_level", "price_range"])
    target_audience = safe_get(raw_competitor, ["target_audience"])
    sentiment_summary = safe_get(raw_competitor, ["sentiment_summary"])

    if rating is None:
        quality_report["missing_fields"].append({
            "section": "competitors",
            "competitor": name,
            "field": "rating",
        })

    if review_count is None:
        quality_report["missing_fields"].append({
            "section": "competitors",
            "competitor": name,
            "field": "review_count",
        })

    raw_reviews_sample = safe_get(
        raw_competitor, ["reviews_sample", "reviews", "sample_reviews"]
    )

    reviews_sample = normalize_reviews_collection(
        raw_reviews_sample,
        entity_name=name,
        entity_type="competitor",
        source="competitor_reviews_sample",
        quality_report=quality_report,
    )

    if review_count is not None and len(reviews_sample) > 0:
        # Not necessarily an error, but flag large discrepancies for review
        if review_count < len(reviews_sample):
            quality_report["mismatches"].append({
                "section": "competitors",
                "competitor": name,
                "issue": "review_count smaller than number of sample reviews provided",
                "review_count": review_count,
                "sample_size": len(reviews_sample),
            })

    return {
        "name": name,
        "positioning": positioning if positioning is not None else "unknown",
        "price_level": price_level if price_level is not None else "unknown",
        "rating": rating,
        "review_count": review_count,
        "address": address if address is not None else "unknown",
        "target_audience": target_audience if target_audience is not None else "unknown",
        "sentiment_summary": sentiment_summary if isinstance(sentiment_summary, dict) else {},
        "reviews_sample": reviews_sample,
    }


def normalize_competitors(raw_data, quality_report):
    raw_competitors = safe_get(raw_data, ["competitors"])

    if raw_competitors is None:
        return []

    if isinstance(raw_competitors, dict):
        # Could be keyed dict of competitors
        if all(isinstance(v, dict) for v in raw_competitors.values()):
            raw_competitors = list(raw_competitors.values())
        else:
            raw_competitors = []

    if not isinstance(raw_competitors, list):
        quality_report["mismatches"].append({
            "section": "competitors",
            "issue": "competitors field is not a list",
        })
        return []

    normalized = []
    for idx, raw_comp in enumerate(raw_competitors):
        comp = normalize_competitor(raw_comp, idx, quality_report)
        if comp is not None:
            normalized.append(comp)

    return normalized


# ---------------------------------------------------------------------------
# Business reviews normalization
# ---------------------------------------------------------------------------

def normalize_business_reviews(raw_data, business_name, quality_report):
    raw_reviews = safe_get(raw_data, ["business_reviews", "reviews"])

    # Some schemas nest reviews under 'reviews': {'items': [...]} etc.
    return normalize_reviews_collection(
        raw_reviews,
        entity_name=business_name if business_name else "unknown",
        entity_type="target_business",
        source="business_reviews",
        quality_report=quality_report,
    )


# ---------------------------------------------------------------------------
# Evidence refs normalization
# ---------------------------------------------------------------------------

def normalize_evidence_refs(raw_data, quality_report):
    raw_refs = safe_get(raw_data, ["evidence_refs", "evidence", "refs"])

    if raw_refs is None:
        return []

    if isinstance(raw_refs, dict):
        for key in ["items", "list", "refs"]:
            if key in raw_refs and isinstance(raw_refs[key], list):
                raw_refs = raw_refs[key]
                break
        else:
            raw_refs = []

    if not isinstance(raw_refs, list):
        quality_report["mismatches"].append({
            "section": "evidence_refs",
            "issue": "evidence_refs field is not a list",
        })
        return []

    normalized = []
    for idx, ref in enumerate(raw_refs):
        if isinstance(ref, dict):
            normalized.append({
                "ref_id": safe_get(ref, ["ref_id", "id"], f"ref_{idx}"),
                "type": safe_get(ref, ["type", "ref_type"], "unknown"),
                "value": safe_get(ref, ["value", "url", "source", "text"], None),
                "description": clean_text(safe_get(ref, ["description", "note"])),
            })
        else:
            normalized.append({
                "ref_id": f"ref_{idx}",
                "type": "unknown",
                "value": ref,
                "description": None,
            })

    return normalized


# ---------------------------------------------------------------------------
# Duplicate detection across all reviews
# ---------------------------------------------------------------------------

def detect_duplicates(all_reviews, quality_report):
    """
    Detects exact duplicates (via normalized hash) and near-duplicates
    (via Jaccard similarity above SIMILARITY_THRESHOLD) across the full
    set of normalized reviews. Annotates quality_report['duplicates_found'].
    """
    seen_hashes = {}
    duplicate_groups = []

    # Exact duplicate detection via hash
    for review in all_reviews:
        text = review.get("clean_text") or ""
        if not text.strip():
            continue
        h = text_hash(text)
        seen_hashes.setdefault(h, []).append(review["review_id"])

    for h, ids in seen_hashes.items():
        if len(ids) > 1:
            duplicate_groups.append({
                "type": "exact",
                "review_ids": ids,
            })

    # Near-duplicate detection via similarity (only among non-exact-dupe items,
    # and capped to avoid O(n^2) blowups on very large datasets)
    n = len(all_reviews)
    MAX_PAIRWISE = 4000  # safety cap on number of comparisons

    if n <= 200:  # only run pairwise comparison for reasonably sized sets
        comparisons = 0
        flagged_pairs = set()
        for i in range(n):
            text_i = all_reviews[i].get("clean_text") or ""
            if not text_i.strip():
                continue
            for j in range(i + 1, n):
                if comparisons >= MAX_PAIRWISE:
                    break
                comparisons += 1
                text_j = all_reviews[j].get("clean_text") or ""
                if not text_j.strip():
                    continue
                if all_reviews[i]["entity_name"] != all_reviews[j]["entity_name"]:
                    continue
                sim = text_similarity(text_i, text_j)
                if sim >= SIMILARITY_THRESHOLD:
                    pair = tuple(sorted([all_reviews[i]["review_id"], all_reviews[j]["review_id"]]))
                    if pair not in flagged_pairs:
                        flagged_pairs.add(pair)
                        duplicate_groups.append({
                            "type": "near_duplicate",
                            "review_ids": list(pair),
                            "similarity": round(sim, 3),
                        })

    quality_report["duplicates_found"] = duplicate_groups

    # Mark duplicate items as needing manual review (except the first in each group)
    flagged_ids = set()
    for group in duplicate_groups:
        ids = group["review_ids"]
        for dup_id in ids[1:]:
            flagged_ids.add(dup_id)

    for review in all_reviews:
        if review["review_id"] in flagged_ids:
            review["usable_for_analysis"] = False
            quality_report["manual_review_needed"].append({
                "review_id": review["review_id"],
                "entity_name": review["entity_name"],
                "entity_type": review["entity_type"],
                "reasons": ["duplicate_or_near_duplicate"],
            })


# ---------------------------------------------------------------------------
# Quality report assembly
# ---------------------------------------------------------------------------

def init_quality_report():
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "missing_fields": [],
        "duplicates_found": [],
        "synthetic_items": [],
        "mismatches": [],
        "manual_review_needed": [],
        "confidence_notes": [],
    }


def finalize_quality_report(quality_report, raw_data, business_profile,
                             business_reviews, competitors, evidence_refs):
    notes = quality_report["confidence_notes"]

    notes.append(
        f"Total business reviews processed: {len(business_reviews)}."
    )
    notes.append(
        f"Total competitors processed: {len(competitors)}."
    )

    total_competitor_reviews = sum(len(c.get("reviews_sample", [])) for c in competitors)
    notes.append(
        f"Total competitor sample reviews processed: {total_competitor_reviews}."
    )

    if not business_reviews:
        notes.append("No business reviews were found; sentiment-based "
                      "analysis for the target business will be limited.")

    unusable = [r for r in business_reviews if not r.get("usable_for_analysis")]
    if unusable:
        notes.append(
            f"{len(unusable)} of {len(business_reviews)} business reviews "
            f"were flagged as not usable for analysis."
        )

    if quality_report["duplicates_found"]:
        notes.append(
            f"{len(quality_report['duplicates_found'])} duplicate/near-duplicate "
            f"review group(s) detected."
        )

    if quality_report["synthetic_items"]:
        notes.append(
            f"{len(quality_report['synthetic_items'])} review(s) flagged as "
            f"potentially synthetic or placeholder content."
        )

    if quality_report["mismatches"]:
        notes.append(
            f"{len(quality_report['mismatches'])} structural mismatch(es) "
            f"detected in the source data."
        )

    if quality_report["missing_fields"]:
        notes.append(
            f"{len(quality_report['missing_fields'])} missing field "
            f"occurrence(s) detected across the dataset."
        )

    # Pre-existing 'confidence' info from source data, if any
    pre_existing_confidence = safe_get(raw_data, ["confidence"])
    if isinstance(pre_existing_confidence, dict) and pre_existing_confidence:
        quality_report["source_confidence"] = pre_existing_confidence

    # Pre-existing quality_report from source data, if any (preserved separately)
    pre_existing_quality = safe_get(raw_data, ["quality_report"])
    if isinstance(pre_existing_quality, dict) and pre_existing_quality:
        quality_report["source_quality_report"] = pre_existing_quality

    quality_report["summary_counts"] = {
        "business_reviews_total": len(business_reviews),
        "business_reviews_usable": len(business_reviews) - len(unusable),
        "competitors_total": len(competitors),
        "competitor_reviews_total": total_competitor_reviews,
        "evidence_refs_total": len(evidence_refs),
        "missing_field_occurrences": len(quality_report["missing_fields"]),
        "duplicate_groups": len(quality_report["duplicates_found"]),
        "synthetic_items": len(quality_report["synthetic_items"]),
        "mismatches": len(quality_report["mismatches"]),
        "manual_review_items": len(quality_report["manual_review_needed"]),
    }

    return quality_report


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def load_input(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse input file '{input_path}' as JSON: {e}"
        )


def normalize_dataset(raw_data):
    if not isinstance(raw_data, dict):
        raise ValueError("Input data must be a JSON object at the top level.")

    quality_report = init_quality_report()

    business_profile = normalize_business_profile(raw_data, quality_report)
    business_name = business_profile.get("business_name") or "unknown"

    business_reviews = normalize_business_reviews(raw_data, business_name, quality_report)
    competitors = normalize_competitors(raw_data, quality_report)
    evidence_refs = normalize_evidence_refs(raw_data, quality_report)

    # Aggregate all reviews (business + competitor samples) for duplicate detection
    all_reviews = list(business_reviews)
    for comp in competitors:
        all_reviews.extend(comp.get("reviews_sample", []))

    detect_duplicates(all_reviews, quality_report)

    quality_report = finalize_quality_report(
        quality_report, raw_data, business_profile, business_reviews,
        competitors, evidence_refs
    )

    output = {
        "business_profile": business_profile,
        "business_reviews": business_reviews,
        "competitors": competitors,
        "evidence_refs": evidence_refs,
        "quality_report": quality_report,
    }

    return output


def normalize_raw_data(raw_data: dict) -> dict:
    """
    Takes raw input data and returns normalized structured data.

    This is the public, importable entry point for the normalization stage.
    It wraps the existing :func:`normalize_dataset` logic so that other
    modules (e.g. the SWOT pipeline orchestrator) can run normalization
    in-process without going through the CLI / filesystem.

    Args:
        raw_data: A raw, messy business-intelligence dict (scraped profile,
                  reviews, competitor data, etc.).

    Returns:
        A normalized dict with keys: business_profile, business_reviews,
        competitors, evidence_refs, quality_report.
    """
    return normalize_dataset(raw_data)


def write_output(output_data, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: python normalize.py input.json output.json\n")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    try:
        raw_data = load_input(input_path)
    except FileNotFoundError:
        sys.stderr.write(f"Error: input file not found: {input_path}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    try:
        output_data = normalize_dataset(raw_data)
    except Exception as e:
        sys.stderr.write(f"Error during normalization: {e}\n")
        sys.exit(1)

    try:
        write_output(output_data, output_path)
    except OSError as e:
        sys.stderr.write(f"Error writing output file: {e}\n")
        sys.exit(1)

    sys.stdout.write(f"Normalization complete. Output written to: {output_path}\n")


if __name__ == "__main__":
    main()
