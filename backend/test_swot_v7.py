"""
SWOT v7 Test with REAL Gemini LLM
==================================
This test uses Vertex AI Gemini for the LLM enrichment stage.
"""
import os

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

# Verify env is loaded
print("=" * 60)
print("Environment Check")
print("=" * 60)
print(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
print(f"VERTEX_AI_LOCATION:   {os.getenv('VERTEX_AI_LOCATION')}")
print(f"VERTEX_AI_MODEL:      {os.getenv('VERTEX_AI_MODEL')}")

from app.agents.swot import (
    SWOTAgent,
    LLMProvider,
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)


print("\n" + "=" * 60)
print("SWOT v7 with REAL Gemini Test")
print("=" * 60)

# Create test profile
profile = BusinessProfile(
    business_name="Volume Cafe",
    business_type="cafe",
    themes=[
        ReviewTheme(
            theme_category="food_quality",
            entity_type="target_business",
            frequency=15,
            sentiment_balance=SentimentBalance(
                positive=12, negative=2, neutral=1, mixed=0
            ),
        ),
        ReviewTheme(
            theme_category="service",
            entity_type="target_business",
            frequency=10,
            sentiment_balance=SentimentBalance(
                positive=3, negative=6, neutral=1, mixed=0
            ),
        ),
        ReviewTheme(
            theme_category="ambience",
            entity_type="target_business",
            frequency=8,
            sentiment_balance=SentimentBalance(
                positive=7, negative=0, neutral=1, mixed=0
            ),
        ),
        ReviewTheme(
            theme_category="pricing",
            entity_type="target_business",
            frequency=6,
            sentiment_balance=SentimentBalance(
                positive=2, negative=3, neutral=1, mixed=0
            ),
        ),
    ],
)

# Run agent with REAL Gemini
print("\n[1/3] Initializing SWOTAgent (Gemini mode)...")
agent = SWOTAgent(
    provider=LLMProvider.VERTEX_AI,
    model="gemini-2.5-flash",
    dry_run=False,
)

print(f"      Chain size: {len(agent.chain)}")

if not agent.chain:
    print("\n⚠️  WARNING: Chain is empty - will use rule-based fallback")

print("[2/3] Running SWOT pipeline...")
output = agent.run(profile)

print("[3/3] Pipeline complete!\n")

# Show results
print("=" * 60)
print("Results")
print("=" * 60)
print(f"\nEngine Version: {output.engine_version}")
print(f"Business Type: {output.business_type}")
print(f"Provider Used: {output.meta.llm_provider_used}")
print(f"Model Used: {output.meta.llm_model_used}")
print(f"Processing Time: {output.meta.processing_time_ms}ms")
print(f"Fallback Used: {output.meta.fallback_used}")

print(f"\nQuadrant Counts:")
print(f"  Strengths:     {len(output.swot_report.strengths)}")
print(f"  Weaknesses:    {len(output.swot_report.weaknesses)}")
print(f"  Opportunities: {len(output.swot_report.opportunities)}")
print(f"  Threats:       {len(output.swot_report.threats)}")
print(f"  Watchouts:     {len(output.watchouts)}")

# Show all items
print("\n" + "=" * 60)
print("SWOT Analysis Details")
print("=" * 60)

for quadrant_name in ("strengths", "weaknesses", "opportunities", "threats"):
    items = getattr(output.swot_report, quadrant_name)
    if items:
        print(f"\n{quadrant_name.upper()}:")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item.title}")
            print(f"     Reasoning: {item.reasoning[:150]}...")
            print(f"     Score: {item.scoring.strategic_priority:.2f}")

# Strategic summary
print("\n" + "=" * 60)
print("Strategic Summary")
print("=" * 60)
summary = output.strategic_summary
print(f"\nMain Advantage:          {summary.main_advantage}")
print(f"Most Critical Risk:      {summary.most_critical_risk}")
print(f"Best Growth Opportunity: {summary.best_growth_opportunity}")
print(f"Top Strength:            {summary.top_strength}")
print(f"Top Threat:              {summary.top_confirmed_threat}")

print("\n" + "=" * 60)
if not output.meta.fallback_used:
    print("✅ SWOT v7 with REAL Gemini WORKS!")
else:
    print("⚠️  Used rule-based fallback (Gemini not configured)")
print("=" * 60)