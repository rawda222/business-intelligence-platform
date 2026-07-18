"""
SWOT Evidence Candidate Service Tests
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
    """Build minimal deterministic intelligence for mapping tests."""

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
        ),
        TrendSourceCoverage(
            source="facebook",
            available=facebook_available,
            post_count=(
                4
                if facebook_available
                else 0
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
        ),
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
        new_sources_since_baseline=tuple(
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
        ),
        warnings=(),
    )


def test_publishing_growth_becomes_strength_candidate():
    """Increasing publishing should produce a reviewed strength."""

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

    candidate = candidates[0]

    assert (
        candidate.disposition
        == "swot_candidate"
    )

    assert candidate.quadrant == "strength"

    assert (
        candidate.mapping_rule
        == "publishing_growth_to_strength_v1"
    )

    assert candidate.supporting_sources == (
        "facebook",
        "instagram",
    )

    assert candidate.requires_manual_review


def test_publishing_decline_becomes_weakness_candidate():
    """Declining publishing should produce a reviewed weakness."""

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

    assert candidate.quadrant == "weakness"

    assert (
        candidate.mapping_rule
        == "publishing_decline_to_weakness_v1"
    )


def test_rating_decline_becomes_review_weakness():
    """A declining rating should remain grounded in reviews."""

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

    assert candidate.quadrant == "weakness"

    assert candidate.supporting_sources == (
        "google_maps_reviews",
    )

    assert (
        candidate.evidence_references
        == (
            "insight:rating_direction",
        )
    )


def test_low_review_volume_is_data_gap():
    """Low review volume must not become a SWOT weakness."""

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
        candidate.mapping_rule
        == "low_review_volume_to_gap_v1"
    )


def test_peak_reactions_is_supporting_signal_only():
    """A single engagement peak must not become a strength."""

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
        candidate.mapping_rule
        == "peak_reactions_to_support_v1"
    )


def test_zero_posts_without_social_data_is_gap():
    """Absent scraper data must not create a false weakness."""

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

    assert candidate.supporting_sources == ()
