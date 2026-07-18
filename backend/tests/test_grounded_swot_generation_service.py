"""
Grounded SWOT Generation Service Tests
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)
from app.services.grounded_swot_generation_service import (
    generate_grounded_swot,
)


_BUSINESS_ID = UUID(
    "84848484-8484-8484-8484-848484848484"
)


class FakeSwotAgent:
    """Deterministic SWOT Agent replacement."""

    def __init__(
        self,
        output,
    ):
        self.output = output

        self.received_profile = None

    def run(
        self,
        profile,
    ):
        self.received_profile = profile

        return self.output


def _theme() -> ReviewTheme:
    """Build one negative customer theme."""

    return ReviewTheme(
        theme_category="service_speed",
        entity_type="target_business",
        frequency=3,
        sentiment_balance=(
            SentimentBalance(
                positive=0,
                negative=3,
                neutral=0,
                mixed=0,
            )
        ),
        confidence_score=0.8,
        evidence_refs=[
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ],
        source_platforms=[
            "google_maps",
            "facebook",
            "instagram",
        ],
    )


def _bundle():
    """Build the minimum generation bundle."""

    profile = BusinessProfile(
        business_name="Example Cafe",
        business_type="cafe",
        themes=[
            _theme()
        ],
        allowed_evidence_references=[
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ],
        source_coverage=[
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ],
    )

    return SimpleNamespace(
        business_id=_BUSINESS_ID,
        swot_profile=profile,
        trend_candidates=(),
        allowed_evidence_references=(
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ),
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
        warnings=(),
    )


def _item(
    *,
    evidence_refs: list[str],
    source_theme: str = "service_speed",
) -> dict:
    """Build one generated SWOT item."""

    return {
        "title": (
            "Recurring service delays"
        ),
        "reasoning": (
            "Customer evidence repeatedly "
            "mentions slow service."
        ),
        "source_theme": source_theme,
        "quadrant": "weaknesses",
        "tags": [
            "service",
            "operations",
        ],
        "scoring": {
            "importance": 8.0,
            "impact": 7.0,
            "confidence": 0.95,
        },
        "evidence_refs": (
            evidence_refs
        ),
        "frequency": 999,
    }


def _generated_output(
    *,
    weaknesses: list | None = None,
    provider: str = "vertex_ai",
    model: str = "gemini-2.5-flash",
    fallback_used: bool = False,
) -> dict:
    """Build one generated SWOT output."""

    return {
        "swot_report": {
            "strengths": [],
            "weaknesses": (
                weaknesses or []
            ),
            "opportunities": [],
            "threats": [],
        },
        "meta": {
            "llm_provider_used": provider,
            "llm_model_used": model,
            "fallback_used": (
                fallback_used
            ),
        },
    }


def test_generates_and_accepts_grounded_item():
    """A grounded agent result should be safe for proposal."""

    bundle = _bundle()

    agent = FakeSwotAgent(
        _generated_output(
            weaknesses=[
                _item(
                    evidence_refs=[
                        "google_maps:review:g-1",
                        "facebook:comment:f-1",
                    ]
                )
            ]
        )
    )

    result = generate_grounded_swot(
        bundle=bundle,
        agent=agent,
    )

    assert (
        agent.received_profile
        is bundle.swot_profile
    )

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert result.provider_used == (
        "vertex_ai"
    )

    assert result.model_used == (
        "gemini-2.5-flash"
    )

    assert not result.fallback_used

    assert result.raw_item_count == 1

    assert (
        result.accepted_item_count
        == 1
    )

    assert result.blocked_item_count == 0

    assert (
        result.safe_for_update_proposal
    )

    accepted = result.accepted_items[0]

    assert accepted.frequency == 3

    assert accepted.confidence == 0.8

    assert not (
        accepted
        .should_feed_strategy_agent
    )


def test_invented_reference_blocks_generation():
    """Invented evidence must make the result unsafe."""

    agent = FakeSwotAgent(
        _generated_output(
            weaknesses=[
                _item(
                    evidence_refs=[
                        "invented:reference"
                    ]
                )
            ]
        )
    )

    result = generate_grounded_swot(
        bundle=_bundle(),
        agent=agent,
    )

    assert (
        result.accepted_item_count
        == 0
    )

    assert result.blocked_item_count == 1

    assert not (
        result.safe_for_update_proposal
    )

    assert (
        "generation:"
        "one_or_more_items_blocked"
        in result.warnings
    )

    assert (
        "generation:"
        "evidence_validation_failed"
        in result.warnings
    )


def test_empty_generation_is_not_safe_for_proposal():
    """An empty SWOT is valid structurally but not useful."""

    result = generate_grounded_swot(
        bundle=_bundle(),
        agent=FakeSwotAgent(
            _generated_output()
        ),
    )

    assert result.raw_item_count == 0

    assert (
        result.accepted_item_count
        == 0
    )

    assert result.blocked_item_count == 0

    assert not (
        result.safe_for_update_proposal
    )

    assert (
        "generation:"
        "no_grounded_items_accepted"
        in result.warnings
    )


def test_rule_based_fallback_is_exposed():
    """Fallback generation must remain visible to reviewers."""

    result = generate_grounded_swot(
        bundle=_bundle(),
        agent=FakeSwotAgent(
            _generated_output(
                weaknesses=[
                    _item(
                        evidence_refs=[
                            "google_maps:review:g-1"
                        ]
                    )
                ],
                provider="rule_based",
                model="n/a",
                fallback_used=True,
            )
        ),
    )

    assert result.fallback_used

    assert result.provider_used == (
        "rule_based"
    )

    assert result.model_used == "n/a"

    assert (
        "generation:"
        "rule_based_fallback_used"
        in result.warnings
    )

    assert (
        result.safe_for_update_proposal
    )


def test_bundle_warnings_are_preserved():
    """Input warnings should remain visible after generation."""

    bundle = _bundle()

    bundle.warnings = (
        "customer_voice:"
        "low_quality_comment",
    )

    result = generate_grounded_swot(
        bundle=bundle,
        agent=FakeSwotAgent(
            _generated_output()
        ),
    )

    assert (
        "customer_voice:"
        "low_quality_comment"
        in result.warnings
    )


def test_missing_report_is_rejected_by_validator():
    """Malformed agent output must fail closed."""

    result = generate_grounded_swot(
        bundle=_bundle(),
        agent=FakeSwotAgent(
            {
                "unexpected": "value",
                "meta": {
                    "llm_provider_used": (
                        "vertex_ai"
                    ),
                    "llm_model_used": (
                        "gemini-2.5-flash"
                    ),
                    "fallback_used": False,
                },
            }
        ),
    )

    assert not (
        result.safe_for_update_proposal
    )

    assert any(
        violation.code
        == "missing_swot_report"
        for violation
        in result
        .validation
        .violations
    )


def test_agent_without_run_method_is_rejected():
    """Generation dependencies must expose run(profile)."""

    with pytest.raises(
        TypeError,
        match="run",
    ):
        generate_grounded_swot(
            bundle=_bundle(),
            agent=object(),
        )


def test_generated_output_is_preserved_for_audit():
    """The original generated output should remain auditable."""

    generated = _generated_output(
        weaknesses=[
            _item(
                evidence_refs=[
                    "google_maps:review:g-1"
                ]
            )
        ]
    )

    result = generate_grounded_swot(
        bundle=_bundle(),
        agent=FakeSwotAgent(
            generated
        ),
    )

    assert (
        result.generated_output
        is generated
    )

    assert (
        result
        .allowed_evidence_references
        == _bundle()
        .allowed_evidence_references
    )

    assert result.source_coverage == (
        "business_profile",
        "google_maps_reviews",
        "facebook",
        "instagram",
    )
