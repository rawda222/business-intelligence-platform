"""
Normalize - Main Pipeline
=========================
Top-level orchestration for the data normalization process.

The pipeline:
1. Validates input
2. Initializes quality report
3. Normalizes business profile
4. Normalizes business reviews
5. Normalizes competitors (with their reviews)
6. Normalizes evidence references
7. Detects duplicates across all reviews
8. Finalizes quality report
9. Returns unified normalized dataset
"""
from app.preprocessing.normalize.helpers import safe_get
from app.preprocessing.normalize.business import normalize_business_profile
from app.preprocessing.normalize.competitors import normalize_competitors
from app.preprocessing.normalize.reviews import normalize_reviews_collection
from app.preprocessing.normalize.duplicates import detect_duplicates
from app.preprocessing.normalize.quality import (
    init_quality_report,
    finalize_quality_report,
)


def normalize_business_reviews(raw_data: dict, business_name: str, quality_report: dict) -> list:
    """
    Normalize the target business's reviews.
    """
    raw_reviews = safe_get(raw_data, ["business_reviews", "reviews"])
    
    return normalize_reviews_collection(
        raw_reviews=raw_reviews,
        entity_name=business_name or "target_business",
        entity_type="target_business",
        source=safe_get(raw_data, ["source"]) or "business_data",
        quality_report=quality_report,
    )


def normalize_evidence_refs(raw_data: dict, quality_report: dict) -> list:
    """
    Normalize evidence references (links, citations, attachments).
    """
    raw_refs = safe_get(raw_data, ["evidence_refs", "evidence", "refs"])
    
    if raw_refs is None:
        return []
    
    if not isinstance(raw_refs, list):
        quality_report["mismatches"].append({
            "section": "evidence_refs",
            "issue": "evidence_refs is not a list",
        })
        return []
    
    normalized = []
    for index, ref in enumerate(raw_refs):
        if isinstance(ref, str):
            normalized.append({
                "id": f"ref_{index}",
                "type": "url" if ref.startswith("http") else "text",
                "value": ref,
            })
        elif isinstance(ref, dict):
            normalized.append({
                "id": safe_get(ref, ["id"]) or f"ref_{index}",
                "type": safe_get(ref, ["type"]) or "unknown",
                "value": safe_get(ref, ["value", "url", "content"]) or "",
                "description": safe_get(ref, ["description"]),
            })
    
    return normalized


def normalize_raw_data(raw_data: dict) -> dict:
    """
    Main entry point: normalize a complete raw business intelligence dataset.
    
    Args:
        raw_data: Raw scraped/collected business data
    
    Returns:
        Normalized dataset with:
        - business_profile
        - business_reviews
        - competitors (each with reviews_sample)
        - evidence_refs
        - quality_report
    
    Raises:
        ValueError: If raw_data is not a dict
    """
    if not isinstance(raw_data, dict):
        raise ValueError("Input data must be a JSON object at the top level.")
    
    # Initialize quality report
    quality_report = init_quality_report()
    
    # 1. Normalize business profile
    business_profile = normalize_business_profile(raw_data, quality_report)
    
    # Get business name for review attribution
    business_name = (
        safe_get(business_profile.get("business_identity", {}), ["name"])
        or "target_business"
    )
    
    # 2. Normalize target business reviews
    business_reviews = normalize_business_reviews(
        raw_data,
        business_name,
        quality_report,
    )
    
    # 3. Normalize competitors (including their reviews)
    competitors = normalize_competitors(raw_data, quality_report)
    
    # 4. Normalize evidence references
    evidence_refs = normalize_evidence_refs(raw_data, quality_report)
    
    # 5. Collect all reviews for duplicate detection
    all_reviews = list(business_reviews)
    for comp in competitors:
        all_reviews.extend(comp.get("reviews_sample", []))
    
    # 6. Detect duplicates across all reviews
    detect_duplicates(all_reviews, quality_report)
    
    # 7. Finalize quality report
    finalize_quality_report(
        quality_report,
        raw_data,
        business_profile,
        business_reviews,
        competitors,
        evidence_refs,
    )
    
    # 8. Return unified output
    return {
        "business_profile": business_profile,
        "business_reviews": business_reviews,
        "competitors": competitors,
        "evidence_refs": evidence_refs,
        "quality_report": quality_report,
    }