"""
SWOT Evidence Candidate Service Tests

Verifies that deterministic brand-trend evidence is converted into
conservative, quality-gated SWOT candidates without calling an LLM
or modifying an existing SWOT report.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.services.business_trend_intelligence_service import (
    BusinessTrendIntelligence,
    TrendSourceCoverage,
)
from app.services.swot_evidence_candidate_service import (
    build_swot_evidence_candidates,
)
from app.services.trend_evidence_service import (
    TrendEvidence,
)


_BUSINESS_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

_RANGE_START = datetime(
    2026,
    6,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    9,
    1,
    tzinfo=UTC,
)


def _intelligence(
    evidence: list[TrendEvidence],
    *,
    facebook_available: bool = True,
    instagram_available: bool = True,
    reviews_available: bool = True,
) -> BusinessTrendIntelligence:
    """
    Build minimal deterministic intelligence for candidate tests.

    The report is not accessed by the candidate service, so a plain
    object is sufficient for this isolated mapping-layer test.
    """

    coverage = (
        TrendSourceCoverage(
            source="business_profile",
            available=True,
        ),
        TrendSourceCoverage(
            source="google_maps_reviews",
            available=reviews_available,
            review_count=(
                8
                if reviews_available
                else 0
            ),
            references=(
                "reviews_by_source:google_maps",
            ),
        ),
        TrendSourceCoverage(
            source="facebook",
            available=facebook_available,
            post_count=(
                4
                if facebook_available
                else 0
            ),
            comment_count=(
                2
                if facebook_available
                else 0
            ),
            references=(
                "posts_by_platform:facebook",
                "comments_by_platform:facebook",
            ),
        ),
        TrendSourceCoverage(
            source="instagram",
            available=instagram_available,
            post_count=(
                6
                if instagram_available
                else 0
            ),
            comment_count=(
                3
                if instagram_available
                else 0
            ),
            references=(
                "posts_by_platform:instagram",
                "comments_by_platform:instagram",
            ),
        ),
    )

    new_sources = tuple(
        source
        for source, available
        in (
            (
                "facebook",
                facebook_available,
            ),
            (
                "instagram",
                instagram_available,
            ),
        )
        if available
    )

    return BusinessTrendIntelligence(
        business_id=_BUSINESS_ID,
        range_start=_RANGE_START,
        range_end=_RANGE_END,
        report=object(),
        insights=(),
        evidence=tuple(
            evidence
        ),
        source_coverage=coverage,
        baseline_sources=(
            "business_profile",
            "google_maps_reviews",
        ),
        new_sources_since_baseline=(
            new_sources
        ),
        warnings=(),
    )


def test_publishing_growth_becomes_strength_candidate():
    """
    Increasing publishing should produce a reviewed Strength.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="positive",
        confidence=0.7,
        metric=(
            "publishing_trend_direction"
        ),
        value="info",
        reference=(
            "insight:publishing_trend"
        ),
        description=(
            "Publishing activity increased."
        ),
        supporting_metrics={
            "first_half_posts": 3,
            "second_half_posts": 7,
        },
    )

    candidates = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert (
        candidate.business_id
        == _BUSINESS_ID
    )

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "strength"

    assert (
        candidate.title
        == "Increasing publishing activity"
    )

    assert (
        candidate.mapping_rule
        == "publishing_growth_to_strength_v1"
    )

    assert candidate.supporting_sources == (
        "facebook",
        "instagram",
    )

    assert candidate.supporting_metrics == (
        (
            "first_half_posts",
            3,
        ),
        (
            "second_half_posts",
            7,
        ),
    )

    assert (
        candidate.evidence_references
        == (
            "insight:publishing_trend",
        )
    )

    assert candidate.confidence == 0.7

    assert (
        candidate.claim_strength
        == "internally_supported"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review


def test_validated_multi_source_candidate_can_feed_strategy():
    """
    High-confidence evidence from both social datasets may pass
    the deterministic Strategy eligibility gate.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="positive",
        confidence=0.85,
        metric=(
            "publishing_trend_direction"
        ),
        value="info",
        reference=(
            "insight:publishing_trend"
        ),
        description=(
            "Publishing activity increased."
        ),
        supporting_metrics={
            "first_half_posts": 4,
            "second_half_posts": 10,
        },
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence],
                facebook_available=True,
                instagram_available=True,
            )
        )[0]
    )

    assert candidate.quadrant == "strength"

    assert candidate.supporting_sources == (
        "facebook",
        "instagram",
    )

    assert candidate.confidence == 0.85

    assert (
        candidate.claim_strength
        == "validated"
    )

    assert candidate.decision == "eligible"

    assert (
        candidate
        .should_feed_strategy_agent
    )

    assert not candidate.requires_manual_review


def test_single_source_high_confidence_requires_review():
    """
    High confidence from one social source alone should not pass
    the multi-source Strategy gate.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="positive",
        confidence=0.9,
        metric=(
            "publishing_trend_direction"
        ),
        value="info",
        reference=(
            "insight:publishing_trend"
        ),
        description=(
            "Publishing activity increased."
        ),
        supporting_metrics={
            "first_half_posts": 2,
            "second_half_posts": 8,
        },
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence],
                facebook_available=True,
                instagram_available=False,
            )
        )[0]
    )

    assert candidate.supporting_sources == (
        "facebook",
    )

    assert (
        candidate.claim_strength
        == "internally_supported"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review


def test_publishing_decline_becomes_weakness_candidate():
    """
    Declining publishing should produce a reviewed Weakness.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="negative",
        confidence=0.7,
        metric=(
            "publishing_trend_direction"
        ),
        value="warning",
        reference=(
            "insight:publishing_trend"
        ),
        description=(
            "Publishing activity decreased."
        ),
        supporting_metrics={
            "first_half_posts": 8,
            "second_half_posts": 2,
        },
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "weakness"

    assert (
        candidate.title
        == "Declining publishing activity"
    )

    assert (
        candidate.mapping_rule
        == "publishing_decline_to_weakness_v1"
    )

    assert (
        candidate.claim_strength
        == "internally_supported"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )


def test_zero_posts_with_social_data_becomes_weakness():
    """
    Zero posts may become a Weakness only when social records are
    actually available in the analyzed report.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="negative",
        confidence=0.9,
        metric="total_posts",
        value=0,
        reference=(
            "insight:publishing_activity"
        ),
        description=(
            "No posts were published."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence],
                facebook_available=True,
                instagram_available=True,
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "weakness"

    assert (
        candidate.title
        == "No observed publishing activity"
    )

    assert (
        candidate.mapping_rule
        == "zero_publishing_to_weakness_v1"
    )

    assert candidate.supporting_sources == (
        "facebook",
        "instagram",
    )

    assert (
        candidate.claim_strength
        == "validated"
    )

    assert candidate.decision == "eligible"

    assert (
        candidate
        .should_feed_strategy_agent
    )


def test_zero_posts_without_social_data_is_gap():
    """
    Missing scraper data must not create a false Weakness.
    """

    evidence = TrendEvidence(
        category="publishing",
        direction="negative",
        confidence=0.9,
        metric="total_posts",
        value=0,
        reference=(
            "insight:publishing_activity"
        ),
        description=(
            "No posts were published."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence],
                facebook_available=False,
                instagram_available=False,
            )
        )[0]
    )

    assert candidate.disposition == "data_gap"

    assert candidate.quadrant is None

    assert (
        candidate.title
        == "Social publishing data unavailable"
    )

    assert (
        candidate.mapping_rule
        == "missing_social_data_to_gap_v1"
    )

    assert candidate.supporting_sources == ()

    assert (
        candidate.claim_strength
        == "early_warning"
    )

    assert candidate.decision == "blocked"

    assert not (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review


def test_rating_improvement_becomes_review_strength():
    """
    Improving Google Maps ratings should produce a reviewed
    Strength grounded in review evidence.
    """

    evidence = TrendEvidence(
        category="reviews",
        direction="positive",
        confidence=0.6,
        metric=(
            "rating_average_direction"
        ),
        value="info",
        reference=(
            "insight:rating_direction"
        ),
        description=(
            "Rating average improved."
        ),
        supporting_metrics={
            "first_month_rating_average": 3.9,
            "last_month_rating_average": 4.5,
        },
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "strength"

    assert (
        candidate.title
        == "Improving customer ratings"
    )

    assert candidate.supporting_sources == (
        "google_maps_reviews",
    )

    assert (
        candidate.mapping_rule
        == "rating_improvement_to_strength_v1"
    )

    assert (
        candidate.claim_strength
        == "internally_supported"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )


def test_rating_decline_becomes_review_weakness():
    """
    Declining Google Maps ratings should produce a reviewed
    Weakness grounded in review evidence.
    """

    evidence = TrendEvidence(
        category="reviews",
        direction="negative",
        confidence=0.6,
        metric=(
            "rating_average_direction"
        ),
        value="warning",
        reference=(
            "insight:rating_direction"
        ),
        description=(
            "Rating average declined."
        ),
        supporting_metrics={
            "first_month_rating_average": 4.5,
            "last_month_rating_average": 3.9,
        },
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "weakness"

    assert (
        candidate.title
        == "Declining customer ratings"
    )

    assert candidate.supporting_sources == (
        "google_maps_reviews",
    )

    assert (
        candidate.evidence_references
        == (
            "insight:rating_direction",
        )
    )

    assert (
        candidate.mapping_rule
        == "rating_decline_to_weakness_v1"
    )

    assert (
        candidate.claim_strength
        == "internally_supported"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )


def test_low_review_volume_is_blocked_data_gap():
    """
    Low review volume must not become a SWOT Weakness.
    """

    evidence = TrendEvidence(
        category="reviews",
        direction="negative",
        confidence=0.9,
        metric="total_reviews",
        value=3,
        reference=(
            "insight:review_volume"
        ),
        description=(
            "Review volume is low."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert candidate.disposition == "data_gap"

    assert candidate.quadrant is None

    assert (
        candidate.title
        == "Insufficient customer review volume"
    )

    assert (
        candidate.mapping_rule
        == "low_review_volume_to_gap_v1"
    )

    assert (
        candidate.claim_strength
        == "early_warning"
    )

    assert candidate.decision == "blocked"

    assert not (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review


def test_sufficient_review_volume_is_support_only():
    """
    Review count alone should support rating evidence rather than
    becoming a SWOT item.
    """

    evidence = TrendEvidence(
        category="reviews",
        direction="positive",
        confidence=0.9,
        metric="total_reviews",
        value=12,
        reference=(
            "insight:review_volume"
        ),
        description=(
            "Twelve reviews were captured."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "supporting_signal"
    )

    assert candidate.quadrant is None

    assert (
        candidate.mapping_rule
        == "review_volume_to_support_v1"
    )

    assert (
        candidate.claim_strength
        == "directional_not_validated"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )


def test_peak_reactions_is_supporting_signal_only():
    """
    A single engagement peak must not become a Strength.
    """

    evidence = TrendEvidence(
        category="engagement",
        direction="neutral",
        confidence=0.5,
        metric=(
            "peak_reactions_observed"
        ),
        value=120,
        reference="engagement_curves",
        description=(
            "Peak reactions observed."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "supporting_signal"
    )

    assert candidate.quadrant is None

    assert (
        candidate.title
        == "Observed engagement peak"
    )

    assert (
        candidate.mapping_rule
        == "peak_reactions_to_support_v1"
    )

    assert (
        candidate.claim_strength
        == "directional_not_validated"
    )

    assert (
        candidate.decision
        == "manual_review"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review


def test_unmapped_metric_is_supporting_signal():
    """
    Unknown metrics should remain visible without becoming SWOT
    claims.
    """

    evidence = TrendEvidence(
        category="engagement",
        direction="neutral",
        confidence=0.4,
        metric="unknown_metric",
        value="observed",
        reference="trend:unknown",
        description=(
            "An additional signal was observed."
        ),
    )

    candidate = (
        build_swot_evidence_candidates(
            _intelligence(
                [evidence]
            )
        )[0]
    )

    assert (
        candidate.disposition
        == "supporting_signal"
    )

    assert candidate.quadrant is None

    assert (
        candidate.statement
        == "An additional signal was observed."
    )

    assert (
        candidate.mapping_rule
        == "unmapped_evidence_to_support_v1"
    )

    assert (
        candidate.claim_strength
        == "directional_not_validated"
    )

    assert not (
        candidate
        .should_feed_strategy_agent
    )


def test_candidate_order_matches_evidence_order():
    """
    Candidate order should remain deterministic.
    """

    publishing_evidence = TrendEvidence(
        category="publishing",
        direction="negative",
        confidence=0.7,
        metric=(
            "publishing_trend_direction"
        ),
        value="warning",
        reference=(
            "insight:publishing_trend"
        ),
        description=(
            "Publishing declined."
        ),
        supporting_metrics={
            "first_half_posts": 7,
            "second_half_posts": 2,
        },
    )

    review_evidence = TrendEvidence(
        category="reviews",
        direction="positive",
        confidence=0.6,
        metric=(
            "rating_average_direction"
        ),
        value="info",
        reference=(
            "insight:rating_direction"
        ),
        description=(
            "Ratings improved."
        ),
        supporting_metrics={
            "first_month_rating_average": 3.8,
            "last_month_rating_average": 4.4,
        },
    )

    engagement_evidence = TrendEvidence(
        category="engagement",
        direction="neutral",
        confidence=0.5,
        metric=(
            "peak_reactions_observed"
        ),
        value=80,
        reference="engagement_curves",
        description=(
            "Peak reactions observed."
        ),
    )

    candidates = (
        build_swot_evidence_candidates(
            _intelligence(
                [
                    publishing_evidence,
                    review_evidence,
                    engagement_evidence,
                ]
            )
        )
    )

    assert [
        candidate.mapping_rule
        for candidate in candidates
    ] == [
        "publishing_decline_to_weakness_v1",
        "rating_improvement_to_strength_v1",
        "peak_reactions_to_support_v1",
    ]