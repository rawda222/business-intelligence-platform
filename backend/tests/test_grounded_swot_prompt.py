"""
Grounded SWOT Prompt Tests
"""

import json

from app.agents.swot.prompts.system import (
    SYSTEM_PROMPT,
)
from app.agents.swot.prompts.user import (
    build_user_prompt,
)
from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)


def _profile() -> BusinessProfile:
    """Build one evidence-rich Strong SWOT profile."""

    return BusinessProfile(
        business_name="Example Cafe",
        business_type="cafe",
        themes=[
            ReviewTheme(
                theme_category=(
                    "service_speed"
                ),
                entity_type=(
                    "target_business"
                ),
                frequency=3,
                sentiment_balance=(
                    SentimentBalance(
                        positive=0,
                        negative=3,
                        neutral=0,
                        mixed=0,
                    )
                ),
                confidence_score=0.91,
                representative_quotes=[
                    "Service was slow.",
                    "The order took too long.",
                ],
                source_platforms=[
                    "google_maps",
                    "facebook",
                    "instagram",
                ],
                evidence_refs=[
                    "google_maps:review:g-1",
                    "facebook:comment:f-1",
                    "instagram:comment:i-1",
                ],
            )
        ],
        negative_signals=[
            {
                "theme_category": (
                    "service_speed"
                ),
                "reason": (
                    "high_negative_sentiment"
                ),
            }
        ],
        trend_candidates=[
            {
                "candidate_id": (
                    "trend:publishing_growth"
                ),
                "disposition": (
                    "swot_candidate"
                ),
                "quadrant": "strength",
                "title": (
                    "Increasing publishing activity"
                ),
                "confidence": 0.85,
                "claim_strength": "validated",
                "decision": "eligible",
                "evidence_references": [
                    "insight:publishing_trend"
                ],
                "supporting_sources": [
                    "facebook",
                    "instagram",
                ],
            }
        ],
        source_coverage=[
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ],
        allowed_evidence_references=[
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
            "insight:publishing_trend",
        ],
        analysis_warnings=[],
    )


def _extract_grounding_data(
    prompt: str,
) -> dict:
    """Parse the JSON object embedded after GROUNDING DATA."""

    marker = "GROUNDING DATA:\n"

    start = prompt.index(
        marker
    ) + len(
        marker
    )

    end = prompt.index(
        "\n\nMANDATORY EVIDENCE RULES:",
        start,
    )

    return json.loads(
        prompt[start:end]
    )


def test_prompt_contains_enriched_customer_theme():
    """Customer evidence context should survive prompt building."""

    profile = _profile()

    prompt = build_user_prompt(
        profile=profile,
        kept_themes=profile.themes,
        benchmark_quality="unavailable",
        benchmark_summary={},
    )

    data = _extract_grounding_data(
        prompt
    )

    theme = data[
        "customer_voice_themes"
    ][0]

    assert theme["frequency"] == 3

    assert (
        theme["sentiment_balance"][
            "negative"
        ]
        == 3
    )

    assert (
        theme["confidence_score"]
        == 0.91
    )

    assert theme["source_platforms"] == [
        "google_maps",
        "facebook",
        "instagram",
    ]

    assert theme[
        "representative_quotes"
    ] == [
        "Service was slow.",
        "The order took too long.",
    ]

    assert theme["evidence_refs"] == [
        "google_maps:review:g-1",
        "facebook:comment:f-1",
        "instagram:comment:i-1",
    ]


def test_prompt_contains_trends_allowlist_and_coverage():
    """Trend context and validation boundaries should be explicit."""

    profile = _profile()

    prompt = build_user_prompt(
        profile=profile,
        kept_themes=profile.themes,
        benchmark_quality="unavailable",
        benchmark_summary={},
    )

    data = _extract_grounding_data(
        prompt
    )

    assert len(
        data["brand_trend_candidates"]
    ) == 1

    assert (
        data["brand_trend_candidates"][0][
            "candidate_id"
        ]
        == "trend:publishing_growth"
    )

    assert (
        data[
            "allowed_evidence_references"
        ]
        == profile
        .allowed_evidence_references
    )

    assert data["source_coverage"] == (
        profile.source_coverage
    )


def test_raw_reviews_are_not_included():
    """Full raw reviews should not be copied into the LLM prompt."""

    profile = _profile()

    private_raw_text = (
        "RAW REVIEW TEXT THAT MUST "
        "NOT APPEAR"
    )

    prompt = build_user_prompt(
        profile=profile,
        kept_themes=profile.themes,
        benchmark_quality="unavailable",
        benchmark_summary={},
        raw_reviews=[
            private_raw_text
        ],
    )

    assert private_raw_text not in prompt

    assert (
        "Service was slow."
        in prompt
    )


def test_prompt_defines_ids_not_quotes_as_evidence_refs():
    """The prompt must use the same evidence contract as Python."""

    profile = _profile()

    prompt = build_user_prompt(
        profile=profile,
        kept_themes=profile.themes,
        benchmark_quality="unavailable",
        benchmark_summary={},
    )

    assert (
        "evidence_refs are stable IDs"
        in prompt
    )

    assert (
        "Representative quotes are context only"
        in prompt
    )

    assert (
        "Never put quotes"
        in prompt
    )


def test_system_prompt_forbids_unsupported_claims():
    """System-level grounding rules should remain provider-neutral."""

    assert (
        "Do not use outside knowledge."
        in SYSTEM_PROMPT
    )

    assert (
        "Data gaps are quality warnings"
        in SYSTEM_PROMPT
    )

    assert (
        "Do not generate filler items"
        in SYSTEM_PROMPT
    )

    assert (
        "evidence_refs are stable IDs"
        in SYSTEM_PROMPT
    )
