"""Test Strategy Phase 3 - Prompts."""
from app.agents.strategy.prompts import STRATEGY_SYSTEM_PROMPT, build_strategy_user_prompt


print("=" * 60)
print("Strategy Phase 3 - Prompts Test")
print("=" * 60)

# Mock filtered input
filtered = {
    "business_type": "cafe",
    "validation_status": "PASS",
    "benchmark_quality": "low",
    "strengths": [
        {"item_id": "S1", "title": "Food Quality", "confidence": "validated"},
    ],
    "weaknesses": [
        {"item_id": "W1", "title": "Service Speed", "confidence": "validated"},
    ],
    "opportunities": [
        {"item_id": "O1", "title": "Delivery Market", "confidence": "internally_supported"},
    ],
    "threats": [
        {"item_id": "T1", "title": "New Competitor", "confidence": "directional_not_validated"},
    ],
    "derived_opportunities": [],
    "directional_competitive_signals": [],
}

print(f"\nSystem prompt length: {len(STRATEGY_SYSTEM_PROMPT)} chars")

user_prompt = build_strategy_user_prompt(filtered)
print(f"User prompt length: {len(user_prompt)} chars")

print(f"\nUser prompt preview (first 300 chars):")
print("-" * 60)
print(user_prompt[:300])
print("-" * 60)

print("\n" + "=" * 60)
print("Phase 3 Prompts Test: PASSED")
print("=" * 60)