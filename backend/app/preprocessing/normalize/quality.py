"""
Normalize - Quality Report
==========================
Initialize and finalize the quality report tracking data issues
encountered during normalization.

The quality report contains:
- missing_fields: Fields expected but not found
- duplicates_found: Exact or near-duplicate reviews
- synthetic_items: Reviews flagged as synthetic
- mismatches: Type or schema mismatches
- manual_review_needed: Items requiring human review
- confidence_notes: General confidence observations
"""
from datetime import datetime, timezone


def init_quality_report():
    """
    Initialize a fresh quality report.
    
    Returns:
        Empty quality report dict with all expected keys.
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "missing_fields": [],
        "duplicates_found": [],
        "synthetic_items": [],
        "mismatches": [],
        "manual_review_needed": [],
        "confidence_notes": [],
    }


def finalize_quality_report(
    quality_report,
    raw_data,
    business_profile,
    business_reviews,
    competitors,
    evidence_refs,
):
    """
    Add summary-level confidence notes based on the data quality.
    
    Args:
        quality_report: The quality report dict to finalize
        raw_data: Original raw input
        business_profile: Normalized business profile
        business_reviews: List of normalized reviews
        competitors: List of normalized competitors
        evidence_refs: List of evidence references
    
    Returns:
        The finalized quality_report (modified in place)
    """
    notes = quality_report["confidence_notes"]
    
    # Note 1: Review volume
    review_count = len(business_reviews) if business_reviews else 0
    if review_count == 0:
        notes.append({
            "level": "high",
            "issue": "no_reviews",
            "message": "No business reviews found in input data.",
        })
    elif review_count < 5:
        notes.append({
            "level": "medium",
            "issue": "low_review_volume",
            "message": f"Only {review_count} reviews found. Analysis confidence may be limited.",
        })
    
    # Note 2: Competitor coverage
    competitor_count = len(competitors) if competitors else 0
    if competitor_count == 0:
        notes.append({
            "level": "medium",
            "issue": "no_competitors",
            "message": "No competitor data found. Comparative analysis will not be available.",
        })
    elif competitor_count < 2:
        notes.append({
            "level": "low",
            "issue": "limited_competitors",
            "message": f"Only {competitor_count} competitor(s). Benchmarking coverage is limited.",
        })
    
    # Note 3: Synthetic content rate
    synthetic_count = len(quality_report["synthetic_items"])
    if review_count > 0 and synthetic_count / review_count > 0.3:
        notes.append({
            "level": "high",
            "issue": "high_synthetic_rate",
            "message": f"{synthetic_count}/{review_count} reviews appear synthetic. Data quality is questionable.",
        })
    
    # Note 4: Duplicate rate
    dup_groups = quality_report["duplicates_found"]
    if review_count > 0 and len(dup_groups) > 0:
        notes.append({
            "level": "medium",
            "issue": "duplicates_present",
            "message": f"{len(dup_groups)} duplicate group(s) detected. Consider deduplication.",
        })
    
    # Note 5: Business profile completeness
    if business_profile:
        identity = business_profile.get("business_identity") or {}
        if not identity.get("name"):
            quality_report["missing_fields"].append({
                "section": "business_identity",
                "field": "name",
                "issue": "Business name not found",
            })
    
    return quality_report