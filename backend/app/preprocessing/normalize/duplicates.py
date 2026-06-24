"""
Normalize - Duplicate Detection
===============================
Detect exact and near-duplicate reviews using hashing and Jaccard similarity.

Exact duplicates: SHA256 hash of aggressively normalized text
Near-duplicates: Jaccard similarity above threshold (default 0.85)
"""
import hashlib
import re

from app.preprocessing.normalize.config import SIMILARITY_THRESHOLD


def normalize_for_hash(text: str) -> str:
    """
    Aggressively normalize text purely for duplicate-detection hashing.
    
    Steps:
    - Lowercase
    - Strip all non-alphanumeric (preserving Arabic)
    - Collapse whitespace
    """
    if not text:
        return ""
    
    t = text.lower()
    # Keep word characters and Arabic range
    t = re.sub(r'[^\w\u0600-\u06FF]+', ' ', t, flags=re.UNICODE)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    
    return t


def text_hash(text: str) -> str:
    """
    Generate a SHA256 hash of normalized text for exact-duplicate detection.
    """
    norm = normalize_for_hash(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def text_similarity(a: str, b: str) -> float:
    """
    Calculate Jaccard similarity between two texts.
    
    Lightweight, dependency-free near-duplicate detector.
    Uses word-set intersection / union.
    
    Returns:
        Similarity score between 0.0 and 1.0
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


def detect_duplicates(all_reviews, quality_report):
    """
    Detect exact and near-duplicate reviews.
    
    Process:
    1. Find exact duplicates via normalized hash
    2. Find near-duplicates via Jaccard similarity above SIMILARITY_THRESHOLD
    
    Annotates quality_report['duplicates_found'] with detected groups.
    
    Args:
        all_reviews: List of normalized review dicts
        quality_report: Quality report dict to annotate
    
    Returns:
        Number of duplicates detected
    """
    seen_hashes = {}
    duplicate_groups = []
    
    # Step 1: Find exact duplicates by hash
    for review in all_reviews:
        text = review.get("clean_text") or review.get("text") or ""
        if not text or not text.strip():
            continue
        
        h = text_hash(text)
        review_id = review.get("review_id", "unknown")
        
        if h in seen_hashes:
            seen_hashes[h].append(review_id)
        else:
            seen_hashes[h] = [review_id]
    
    # Collect groups with 2+ members (exact duplicates)
    for h, members in seen_hashes.items():
        if len(members) > 1:
            duplicate_groups.append({
                "type": "exact",
                "review_ids": members,
                "hash": h,
            })
    
    # Step 2: Find near-duplicates by Jaccard similarity
    # Only check reviews that aren't already in exact-duplicate groups
    already_grouped = set()
    for group in duplicate_groups:
        already_grouped.update(group["review_ids"])
    
    ungrouped_reviews = [
        r for r in all_reviews
        if r.get("review_id") not in already_grouped
        and (r.get("clean_text") or r.get("text"))
    ]
    
    near_duplicate_pairs = []
    n = len(ungrouped_reviews)
    
    for i in range(n):
        for j in range(i + 1, n):
            text_a = ungrouped_reviews[i].get("clean_text") or ungrouped_reviews[i].get("text") or ""
            text_b = ungrouped_reviews[j].get("clean_text") or ungrouped_reviews[j].get("text") or ""
            
            if not text_a or not text_b:
                continue
            
            sim = text_similarity(text_a, text_b)
            if sim >= SIMILARITY_THRESHOLD:
                near_duplicate_pairs.append({
                    "type": "near",
                    "review_ids": [
                        ungrouped_reviews[i].get("review_id"),
                        ungrouped_reviews[j].get("review_id"),
                    ],
                    "similarity": round(sim, 3),
                })
    
    duplicate_groups.extend(near_duplicate_pairs)
    
    # Annotate quality report
    if duplicate_groups:
        quality_report["duplicates_found"].extend(duplicate_groups)
    
    return len(duplicate_groups)