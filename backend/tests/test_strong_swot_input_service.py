"""
Strong SWOT Input Service Tests
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.services.business_trend_intelligence_service import (
    BusinessTrendIntelligence,
    TrendSourceCoverage,
)
from app.services.cross_source_customer_voice_service import (
    CrossSourceCustomerVoiceResult,
)
from app.services.strong_swot_input_service import (
    build_strong_swot_input,
)
from app.services.trend_evidence_service import (
    TrendEvidence,
)


_BUSINESS_ID = UUID(
    "51515151-5151-5151-5151-515151515151"
)

_OTHER_BUSINESS_ID = UUID(
    "62626262-6262-6262-6262-626262626262"
)

_RANGE_START = datetime(
    2026,
    7,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    8,
    1,
    tzinfo=UTC,
)


def _normalized_voice_record(
    *,
    review_id: str,
    source: str,
    text: str,
    sentiment_hint: str,
) -> dict:
    """Build one Theme Extractor-compatible customer record."""

    return {
        "review_id": review_id,
        "evidence_reference": (
            review_id
        ),
        "entity_name": "Example Cafe",
        "entity_type": (
            "target_business"
        ),
        "text": text,
        "clean_text": text,
        "rating": None,
        "language": "en",
        "sentiment_hint": (
            sentiment_hint
        ),
        "category_tags": [],
        "is_synthetic": False,
        "usable_for_analysis": True,
        "source": source,
    }


def _customer_voice(
    *,
    business_id: UUID = _BUSINESS_ID,
    warnings: tuple[str, ...] = (),
) -> CrossSourceCustomerVoiceResult:
    """Build deterministic cross-source customer voice."""

    records = (
        _normalized_voice_record(
            review_id=(
                "google_maps:review:g-1"
            ),
            source="google_maps",
            text=(
                "Service was very slow."
            ),
            sentiment_hint="negative",
        ),
        _normalized_voice_record(
            review_id=(
                "facebook:comment:f-1"
            ),
            source="facebook_comments",
            text=(
                "The order took too long."
            ),
            sentiment_hint="negative",
        ),
        _normalized_voice_record(
            review_id=(
                "instagram:comment:i-1"
            ),
            source="instagram_comments",
            text=(
                "Waiting time needs improvement."
            ),
            sentiment_hint="negative",
        ),
    )

    return CrossSourceCustomerVoiceResult(
        business_id=business_id,
        business_name="Example Cafe",
        business_type="cafe",
        business_reviews=records,
        records_received=3,
        records_included=3,
        records_excluded=0,
        duplicate_records=0,
        records_by_source=(
            (
                "google_maps",
                1,
            ),
            (
                "facebook_comments",
                1,
            ),
            (
                "instagram_comments",
                1,
            ),
        ),
        warnings=warnings,
    )


def _trend_intelligence(
    *,
    business_id: UUID = _BUSINESS_ID,
    warnings: tuple[str, ...] = (),
) -> BusinessTrendIntelligence:
    """Build deterministic publishing-trend intelligence."""

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
            "first_half_posts": 3,
            "second_half_posts": 8,
        },
    )

    coverage = (
        TrendSourceCoverage(
            source="business_profile",
            available=True,
        ),
        TrendSourceCoverage(
            source="google_maps_reviews",
            available=True,
            review_count=1,
        ),
        TrendSourceCoverage(
            source="facebook",
            available=True,
            post_count=4,
            comment_count=1,
        ),
        TrendSourceCoverage(
            source="instagram",
            available=True,
            post_count=4,
            comment_count=1,
        ),
    )

    return BusinessTrendIntelligence(
        business_id=business_id,
        range_start=_RANGE_START,
        range_end=_RANGE_END,
        report=object(),
        insights=(),
        evidence=(
            evidence,
        ),
        source_coverage=coverage,
        baseline_sources=(
            "business_profile",
            "google_maps_reviews",
        ),
        new_sources_since_baseline=(
            "facebook",
            "instagram",
        ),
        warnings=warnings,
    )


def _fake_theme_extractor(
    data: dict,
) -> dict:
    """Return one deterministic cross-source customer theme."""

    assert data["business_name"] == (
        "Example Cafe"
    )

    assert len(
        data["business_reviews"]
    ) == 3

    return {
        "themes": [
            {
                "theme_name": (
                    "Service Speed"
                ),
                "theme_category": (
                    "service_speed"
                ),
                "entity_type": (
                    "target_business"
                ),
                "frequency_count": 3,
                "sentiment_distribution": {
                    "positive": 0,
                    "negative": 3,
                    "neutral": 0,
                    "mixed": 0,
                },
                "confidence_score": 0.91,
                "mentions": [
                    "google_maps:review:g-1",
                    "facebook:comment:f-1",
                    "instagram:comment:i-1",
                ],
                "representative_quotes": [
                    "Service was very slow.",
                    "The order took too long.",
                    (
                        "Waiting time needs "
                        "improvement."
                    ),
                ],
            }
        ],
        "positive_signals": [],
        "negative_signals": [
            {
                "theme_category": (
                    "service_speed"
                ),
                "reason": (
                    "high_negative_sentiment"
                ),
            }
        ],
        "opportunity_signals": [],
        "threat_signals": [],
        "comparison_summary": {},
    }


def test_builds_complete_cross_source_swot_input():
    """Customer themes and trends should remain evidence-backed."""

    bundle = build_strong_swot_input(
        customer_voice=_customer_voice(),
        trend_intelligence=(
            _trend_intelligence()
        ),
        theme_extractor=(
            _fake_theme_extractor
        ),
    )

    assert bundle.business_id == (
        _BUSINESS_ID
    )

    assert bundle.range_start == (
        _RANGE_START
    )

    assert bundle.range_end == (
        _RANGE_END
    )

    assert len(
        bundle.swot_profile.themes
    ) == 1

    theme = (
        bundle.swot_profile.themes[0]
    )

    assert theme.frequency == 3

    assert (
        theme.sentiment_balance.negative
        == 3
    )

    assert theme.confidence_score == 0.91

    assert theme.source_platforms == [
        "google_maps",
        "facebook",
        "instagram",
    ]

    assert len(
        bundle.trend_candidates
    ) == 1

    candidate = (
        bundle.trend_candidates[0]
    )

    assert candidate.quadrant == (
        "strength"
    )

    assert (
        candidate
        .should_feed_strategy_agent
    )


def test_allowed_evidence_contains_voice_and_trend_refs():
    """The later LLM validator should receive one strict allowlist."""

    bundle = build_strong_swot_input(
        customer_voice=_customer_voice(),
        trend_intelligence=(
            _trend_intelligence()
        ),
        theme_extractor=(
            _fake_theme_extractor
        ),
    )

    assert (
        bundle.allowed_evidence_references
        == (
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
            "insight:publishing_trend",
        )
    )


def test_source_coverage_is_canonical_and_unique():
    """Observed sources should be exposed once in stable order."""

    bundle = build_strong_swot_input(
        customer_voice=_customer_voice(),
        trend_intelligence=(
            _trend_intelligence()
        ),
        theme_extractor=(
            _fake_theme_extractor
        ),
    )

    assert bundle.source_coverage == (
        "business_profile",
        "google_maps_reviews",
        "facebook",
        "instagram",
    )


def test_cross_business_inputs_are_rejected():
    """Customer voice and trend intelligence must share a tenant."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_strong_swot_input(
            customer_voice=(
                _customer_voice()
            ),
            trend_intelligence=(
                _trend_intelligence(
                    business_id=(
                        _OTHER_BUSINESS_ID
                    )
                )
            ),
            theme_extractor=(
                _fake_theme_extractor
            ),
        )


def test_invalid_theme_extractor_output_is_rejected():
    """The Theme Extractor must return the expected mapping."""

    def invalid_extractor(
        data: dict,
    ):
        del data

        return []

    with pytest.raises(
        ValueError,
        match="mapping",
    ):
        build_strong_swot_input(
            customer_voice=(
                _customer_voice()
            ),
            trend_intelligence=(
                _trend_intelligence()
            ),
            theme_extractor=(
                invalid_extractor
            ),
        )


def test_warnings_are_namespaced_and_deduplicated():
    """Warnings should preserve their origin for later validation."""

    bundle = build_strong_swot_input(
        customer_voice=_customer_voice(
            warnings=(
                "low_quality_comment",
                "low_quality_comment",
            )
        ),
        trend_intelligence=(
            _trend_intelligence(
                warnings=(
                    "No engagement curves.",
                    "No engagement curves.",
                )
            )
        ),
        theme_extractor=(
            _fake_theme_extractor
        ),
    )

    assert bundle.warnings == (
        (
            "customer_voice:"
            "low_quality_comment"
        ),
        (
            "trend_intelligence:"
            "No engagement curves."
        ),
    )


def test_empty_voice_and_themes_produce_quality_warnings():
    """Missing customer voice must be explicit, not fabricated."""

    empty_voice = (
        CrossSourceCustomerVoiceResult(
            business_id=_BUSINESS_ID,
            business_name="Example Cafe",
            business_type="cafe",
            business_reviews=(),
            records_received=0,
            records_included=0,
            records_excluded=0,
            duplicate_records=0,
            records_by_source=(),
            warnings=(),
        )
    )

    def empty_extractor(
        data: dict,
    ) -> dict:
        assert data[
            "business_reviews"
        ] == []

        return {
            "themes": [],
            "positive_signals": [],
            "negative_signals": [],
            "opportunity_signals": [],
            "threat_signals": [],
            "comparison_summary": {},
        }

    bundle = build_strong_swot_input(
        customer_voice=empty_voice,
        trend_intelligence=(
            _trend_intelligence()
        ),
        theme_extractor=(
            empty_extractor
        ),
    )

    assert (
        "customer_voice:"
        "no_usable_records"
        in bundle.warnings
    )

    assert (
        "theme_extractor:"
        "no_themes"
        in bundle.warnings
    )


def test_profile_review_count_uses_included_voice_records():
    """The profile summary must use deduplicated included records."""

    bundle = build_strong_swot_input(
        customer_voice=_customer_voice(),
        trend_intelligence=(
            _trend_intelligence()
        ),
        theme_extractor=(
            _fake_theme_extractor
        ),
    )

    assert (
        bundle
        .swot_profile
        .reviews_summary
        .target_review_count
        == 3
    )