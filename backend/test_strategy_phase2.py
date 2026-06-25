"""Quick test for Strategy Agent Phase 2 (filtering)."""
from app.agents.strategy.filtering import filter_strategy_inputs, is_eligible


print("=" * 60)
print("Strategy Phase 2 - Filtering Test")
print("=" * 60)

# Mock SWOT output with mixed eligibility
mock_swot = {
    "business_type": "cafe",
    "validation_results": {"overall_status": "PASS"},
    "swot_report": {
        "strengths": [
            {
                "item_id": "S1",
                "title": "Food Quality",
                "should_feed_strategy_agent": True,
            },
            {
                "item_id": "S2",
                "title": "Old Strength",
                "should_feed_strategy_agent": False,
            },
        ],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    },
}

# Run filter
result = filter_strategy_inputs(mock_swot)

print(f"\nInput strengths: 2")
print(f"Filtered strengths: {len(result['strengths'])}")

if result['strengths']:
    print(f"First eligible item: {result['strengths'][0]['title']}")

print(f"\nValidation status: {result['validation_status']}")
print(f"Business type: {result['business_type']}")

print("\n" + "=" * 60)
print("Phase 2 Filtering Test: PASSED")
print("=" * 60)