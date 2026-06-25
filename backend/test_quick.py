"""Quick test - doesn't need Docker."""
from app.preprocessing.normalize import normalize_raw_data
from app.preprocessing.theme_extractor import extract_themes_from_normalized

# Test data
data = {
    "business_identity": {"name": "Volume Cafe"},
    "business_reviews": [
        {"text": "Great food and amazing coffee!", "rating": 5},
        {"text": "Slow service but friendly staff", "rating": 4},
        {"text": "Beautiful location with cozy ambience", "rating": 5},
    ],
    "competitors": [
        {
            "name": "Cafe Rival",
            "reviews_sample": [
                {"text": "Cheaper but lower quality", "rating": 3},
                {"text": "Fast service, good prices", "rating": 4},
            ],
        }
    ],
}

print("=" * 60)
print("Testing without Docker (no databases needed)")
print("=" * 60)

print("\n[1/2] Running normalize...")
normalized = normalize_raw_data(data)
print(f"  Reviews: {len(normalized['business_reviews'])}")
print(f"  Competitors: {len(normalized['competitors'])}")

print("\n[2/2] Running theme extractor...")
themes = extract_themes_from_normalized(normalized)
print(f"  Themes found: {len(themes['themes'])}")
print(f"  Positive signals: {len(themes['positive_signals'])}")

if themes['themes']:
    print("\nTop 3 themes:")
    for i, t in enumerate(themes['themes'][:3], 1):
        print(f"  {i}. {t['theme_name']} ({t['entity_type']}) - {t['frequency_count']} mentions")

print("\n" + "=" * 60)
print("SUCCESS! Refactored packages work per")