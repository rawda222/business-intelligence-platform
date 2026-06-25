"""
Scraper Adapter
================
Converts scraper output (from Volume Cafe-style format)
into the standardized format the BI Pipeline expects.
"""
from typing import Any, Dict, List


def adapt_scraper_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert scraper output to BI Pipeline format.

    Supports:
    1. Scraper format (with business_identity, reviews.raw_samples, competitors)
    2. Simple format (business_name + business_reviews directly)

    Returns: Standardized dict ready for pipeline.
    """

    # If already in pipeline format → return as-is
    if "business_reviews" in raw and "business_name" in raw:
        return raw

    output: Dict[str, Any] = {}

    # ============================
    # Business Identity
    # ============================
    identity = raw.get("business_identity", {}) or {}
    output["business_name"] = identity.get("business_name", "Unknown")

    category = identity.get("subcategory") or identity.get("category") or "general"
    output["business_type"] = category.lower()

    # ============================
    # Reviews (from raw_samples or reviews.raw_samples)
    # ============================
    reviews = []

    # Path 1: raw["reviews"]["raw_samples"]
    raw_reviews_block = raw.get("reviews", {}) or {}
    raw_samples = raw_reviews_block.get("raw_samples", []) or []

    # Path 2: raw["raw_samples"]
    if not raw_samples:
        raw_samples = raw.get("raw_samples", []) or []

    # Path 3: raw["business_reviews"]
    if not raw_samples:
        raw_samples = raw.get("business_reviews", []) or []

    for r in raw_samples:
        text = _extract_text(r)
        if text:
            reviews.append({"text": text})

    output["business_reviews"] = reviews

    # ============================
    # Competitors
    # ============================
    competitors = []
    for comp in raw.get("competitors", []) or []:
        comp_name = comp.get("name", "Competitor")
        comp_reviews = []

        for cr in comp.get("reviews_sample", []) or []:
            txt = _extract_text(cr)
            if txt:
                comp_reviews.append({"text": txt})

        competitors.append({
            "name": comp_name,
            "reviews": comp_reviews,
            "rating": comp.get("rating"),
            "positioning": comp.get("positioning"),
        })

    output["competitors"] = competitors

    # ============================
    # Marketing signals (optional)
    # ============================
    if "marketing_signals" in raw:
        output["marketing_signals"] = raw["marketing_signals"]

    if "brand_voice" in raw:
        output["brand_voice"] = raw["brand_voice"]

    if "commercial" in raw:
        output["commercial"] = raw["commercial"]

    return output


def _extract_text(review_item: Any) -> str:
    """
    Reviews can be:
    - {"text": "..."}
    - {"text": {"ar": "..."}}
    - {"text": "{'ar': '...'}"}  (stringified dict)
    - plain string
    """
    if isinstance(review_item, str):
        return _clean_review_text(review_item)

    if isinstance(review_item, dict):
        text = review_item.get("text", "")

        # Case: text is dict {"ar": "..."}
        if isinstance(text, dict):
            return _clean_review_text(text.get("ar") or text.get("en") or "")

        # Case: text is stringified dict
        if isinstance(text, str):
            return _clean_review_text(text)

    return ""


def _clean_review_text(text: str) -> str:
    """
    Clean review text:
    - Remove {'ar': '...'} wrappers
    - Remove escaped newlines
    - Strip whitespace
    """
    if not text:
        return ""

    text = str(text).strip()

    # If it looks like a stringified dict
    if text.startswith("{") and ("'ar'" in text or '"ar"' in text):
        try:
            import ast
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                text = parsed.get("ar") or parsed.get("en") or ""
        except Exception:
            pass

    # Clean escaped newlines
    text = text.replace("\\n", " ").replace("\n", " ")
    text = " ".join(text.split())  # collapse whitespace

    return text.strip()