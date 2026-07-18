"""
Grounded SWOT Output Validator Tests
"""

from types import SimpleNamespace
from uuid import UUID

from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)
from app.services.grounded_swot_output_validator import (
    validate_grounded_swot_output,
)


_BUSINESS_ID = UUID(
    "73737373-7373-7373-7373-737373737373"
)


def _theme(
    *,
    category: str = "service_speed",
    positive: int = 0,
    negative: int = 3,
    confidence: float = 0.8,
) -> ReviewTheme:
    """Build one deterministic customer theme."""

    return ReviewTheme(
        theme_category=category,
        entity_type="target_business",
        frequency=3,
        sentiment_balance=(
            SentimentBalance(
                positive=positive,
                negative=negative,
                neutral=0,
                mixed=0,
            )
        ),
        confidence_score=confidence,
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


def _candidate(
    *,
    candidate_id: str = (
        "trend:publishing_growth"
    ),
    disposition: str = "swot_candidate",
    quadrant: str | None = "strength",
    decision: str = "eligible",
):
    """Build one deterministic trend candidate."""

    return SimpleNamespace(
        candidate_id=candidate_id,
        disposition=disposition,
        quadrant=quadrant,
        confidence=0.85,
        claim_strength="validated",
        decision=decision,
        evidence_references=(
            "insight:publishing_trend",
        ),
        requires_manual_review=(
            decision != "eligible"
        ),
    )


def _bundle(
    *,
    themes: list[ReviewTheme] | None = None,
    candidates: tuple = (),
):
    """Build the minimum bundle required by the validator."""

    profile = BusinessProfile(
        business_name="Example Cafe",
        business_type="cafe",
        themes=(
            themes
            if themes is not None
            else [
                _theme()
            ]
        ),
    )

    references: list[str] = []

    for theme in profile.themes:
        for reference in theme.evidence_refs:
            if reference not in references:
                references.append(
                    reference
                )

    for candidate in candidates:
        for reference in (
            candidate.evidence_references
        ):
            if reference not in references:
                references.append(
                    reference
                )

    return SimpleNamespace(
        business_id=_BUSINESS_ID,
        swot_profile=profile,
        trend_candidates=candidates,
        allowed_evidence_references=tuple(
            references
        ),
    )


def _item(
    *,
    quadrant: str,
    source_theme: str,
    evidence_refs: list[str],
    confidence: float = 0.95,
    frequency: int = 999,
) -> dict:
    """Build one untrusted LLM SWOT item."""

    return {
        "title": "Generated item",
        "reasoning": (
            "Generated reasoning."
        ),
        "source_theme": source_theme,
        "quadrant": quadrant,
        "tags": [
            "one",
            "two",
        ],
        "scoring": {
            "importance": 12,
            "impact": -2,
            "confidence": confidence,
        },
        "evidence_refs": evidence_refs,
        "frequency": frequency,
    }


def _output(
    *,
    strengths: list | None = None,
    weaknesses: list | None = None,
    opportunities: list | None = None,
    threats: list | None = None,
) -> dict:
    """Build one LLM output envelope."""

    return {
        "swot_report": {
            "strengths": strengths or [],
            "weaknesses": weaknesses or [],
            "opportunities": (
                opportunities or []
            ),
            "threats": threats or [],
        }
    }


def test_accepts_grounded_customer_weakness():
    """A negative customer theme may support a Weakness."""

    bundle = _bundle()

    output = _output(
        weaknesses=[
            _item(
                quadrant="weaknesses",
                source_theme="service_speed",
                evidence_refs=[
                    "google_maps:review:g-1",
                    "facebook:comment:f-1",
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert result.valid

    assert len(
        result.accepted_items
    ) == 1

    assert result.blocked_items == ()

    item = result.accepted_items[0]

    assert item.quadrant == (
        "weaknesses"
    )

    assert item.frequency == 3

    assert item.confidence == 0.8

    assert item.importance == 10.0

    assert item.impact == 0.0

    assert (
        item.should_feed_strategy_agent
        is False
    )


def test_unknown_evidence_reference_blocks_item():
    """Invented evidence IDs must fail closed."""

    bundle = _bundle()

    output = _output(
        weaknesses=[
            _item(
                quadrant="weaknesses",
                source_theme="service_speed",
                evidence_refs=[
                    "invented:reference"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert result.accepted_items == ()

    assert len(
        result.blocked_items
    ) == 1

    assert any(
        violation.code
        == "unknown_evidence_reference"
        for violation
        in result.violations
    )


def test_globally_valid_but_wrong_theme_evidence_is_blocked():
    """Evidence must belong to the selected source theme."""

    first_theme = _theme(
        category="service_speed",
    )

    second_theme = ReviewTheme(
        theme_category="product_quality",
        entity_type="target_business",
        frequency=1,
        sentiment_balance=(
            SentimentBalance(
                positive=1,
                negative=0,
                neutral=0,
                mixed=0,
            )
        ),
        confidence_score=0.9,
        evidence_refs=[
            "google_maps:review:quality-1"
        ],
    )

    bundle = _bundle(
        themes=[
            first_theme,
            second_theme,
        ]
    )

    output = _output(
        weaknesses=[
            _item(
                quadrant="weaknesses",
                source_theme="service_speed",
                evidence_refs=[
                    "google_maps:review:quality-1"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "evidence_source_mismatch"
        for violation
        in result.violations
    )


def test_missing_evidence_blocks_item():
    """No SWOT item may pass without evidence IDs."""

    bundle = _bundle()

    output = _output(
        weaknesses=[
            _item(
                quadrant="weaknesses",
                source_theme="service_speed",
                evidence_refs=[],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "missing_evidence"
        for violation
        in result.violations
    )


def test_negative_theme_cannot_become_strength():
    """Quadrant classification must agree with deterministic evidence."""

    bundle = _bundle()

    output = _output(
        strengths=[
            _item(
                quadrant="strengths",
                source_theme="service_speed",
                evidence_refs=[
                    "google_maps:review:g-1"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "incompatible_theme_quadrant"
        for violation
        in result.violations
    )


def test_ordinary_customer_theme_cannot_become_opportunity():
    """Internal themes cannot fabricate an external Opportunity."""

    positive_theme = _theme(
        category="product_quality",
        positive=3,
        negative=0,
    )

    bundle = _bundle(
        themes=[
            positive_theme
        ]
    )

    output = _output(
        opportunities=[
            _item(
                quadrant="opportunities",
                source_theme="product_quality",
                evidence_refs=[
                    "google_maps:review:g-1"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "incompatible_theme_quadrant"
        for violation
        in result.violations
    )


def test_accepts_eligible_trend_candidate():
    """An eligible trend candidate may support its exact quadrant."""

    candidate = _candidate()

    bundle = _bundle(
        candidates=(
            candidate,
        )
    )

    output = _output(
        strengths=[
            _item(
                quadrant="strengths",
                source_theme=(
                    "trend:publishing_growth"
                ),
                evidence_refs=[
                    "insight:publishing_trend"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert result.valid

    assert len(
        result.accepted_items
    ) == 1

    item = result.accepted_items[0]

    assert item.origin == (
        "trend_candidate"
    )

    assert item.claim_strength == (
        "validated"
    )

    assert item.frequency == 0

    assert item.confidence == 0.85


def test_supporting_signal_cannot_become_swot_item():
    """Supporting signals must remain context only."""

    candidate = _candidate(
        candidate_id=(
            "trend:engagement_peak"
        ),
        disposition=(
            "supporting_signal"
        ),
        quadrant=None,
        decision="support_only",
    )

    bundle = _bundle(
        candidates=(
            candidate,
        )
    )

    output = _output(
        strengths=[
            _item(
                quadrant="strengths",
                source_theme=(
                    "trend:engagement_peak"
                ),
                evidence_refs=[
                    "insight:publishing_trend"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "non_actionable_trend_candidate"
        for violation
        in result.violations
    )


def test_unknown_source_theme_blocks_item():
    """The LLM must not invent source themes."""

    bundle = _bundle()

    output = _output(
        weaknesses=[
            _item(
                quadrant="weaknesses",
                source_theme=(
                    "invented_theme"
                ),
                evidence_refs=[
                    "google_maps:review:g-1"
                ],
            )
        ]
    )

    result = validate_grounded_swot_output(
        bundle=bundle,
        llm_output=output,
    )

    assert not result.valid

    assert any(
        violation.code
        == "unknown_source_theme"
        for violation
        in result.violations
    )


def test_missing_report_is_rejected():
    """Malformed LLM output must not be treated as an empty valid SWOT."""

    result = validate_grounded_swot_output(
        bundle=_bundle(),
        llm_output={
            "unexpected": "value"
        },
    )

    assert not result.valid

    assert any(
        violation.code
        == "missing_swot_report"
        for violation
        in result.violations
    )