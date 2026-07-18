"""
Legacy SWOT Adapter Tests
"""

from uuid import UUID

from app.services.legacy_swot_adapter import (
    normalize_legacy_swot,
)


_BUSINESS_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)

_REPORT_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)


def test_v1_item_without_safety_fields_requires_review():
    """
    Lightweight SWOT v1 items must not become Strategy-eligible.
    """

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="1.0",
        swot_report={
            "strengths": [
                {
                    "item_id": "S_001",
                    "title": (
                        "Strong customer satisfaction"
                    ),
                    "reasoning": (
                        "Positive Google Maps reviews."
                    ),
                    "source_theme": (
                        "customer_satisfaction"
                    ),
                    "scoring": {
                        "confidence": 0.9,
                        "strategic_priority": 8,
                    },
                }
            ],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
    )

    assert len(result.items) == 1

    item = result.items[0]

    assert item.item_id == "S_001"

    assert item.quadrant == "strength"

    assert (
        item.claim_strength
        == "directional_not_validated"
    )

    assert item.manual_review_only

    assert not (
        item
        .source_should_feed_strategy_agent
    )

    assert not (
        item
        .should_feed_strategy_agent
    )

    assert item.evidence_references == ()

    assert item.normalization_warnings


def test_v7_validated_item_with_evidence_can_feed_strategy():
    """An explicit validated v7 item should preserve eligibility."""

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="7.0",
        swot_report={
            "strengths": [
                {
                    "item_id": "S_010",
                    "quadrant": "strengths",
                    "title": (
                        "Consistently high service ratings"
                    ),
                    "reasoning": (
                        "Supported by repeated review evidence."
                    ),
                    "source_theme": (
                        "service_quality"
                    ),
                    "scoring": {
                        "confidence": 0.88,
                        "strategic_priority": 8.5,
                    },
                    "evidence_refs": [
                        "review:101",
                        "review:102",
                    ],
                    "claim_strength": "validated",
                    "should_feed_strategy_agent": True,
                    "manual_review_only": False,
                }
            ],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
    )

    item = result.items[0]

    assert item.claim_strength == "validated"

    assert item.confidence == 0.88

    assert item.strategic_priority == 8.5

    assert (
        item.source_should_feed_strategy_agent
    )

    assert (
        item.should_feed_strategy_agent
    )

    assert not item.manual_review_only

    assert item.evidence_references == (
        "review:101",
        "review:102",
    )


def test_directional_manual_review_item_is_blocked():
    """
    A directional item marked for review must not feed Strategy.
    """

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="7.0",
        swot_report={
            "strengths": [],
            "weaknesses": [],
            "opportunities": [
                {
                    "item_id": "O_004",
                    "title": (
                        "Possible unmet customer demand"
                    ),
                    "reasoning": (
                        "Directional evidence only."
                    ),
                    "source_theme": (
                        "customer_demand"
                    ),
                    "scoring": {
                        "confidence": 0.5,
                        "strategic_priority": 6,
                    },
                    "evidence_refs": [
                        "review:201",
                    ],
                    "claim_strength": (
                        "directional_not_validated"
                    ),
                    "should_feed_strategy_agent": True,
                    "manual_review_only": True,
                }
            ],
            "threats": [],
        },
    )

    item = result.items[0]

    assert item.quadrant == "opportunity"

    assert (
        item.source_should_feed_strategy_agent
    )

    assert item.manual_review_only

    assert not (
        item
        .should_feed_strategy_agent
    )


def test_evidence_references_are_normalized_and_unique():
    """Evidence references should be explicit, unique, and ordered."""

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="7.0",
        swot_report={
            "strengths": [],
            "weaknesses": [
                {
                    "item_id": "W_002",
                    "title": (
                        "Recurring service complaints"
                    ),
                    "reasoning": (
                        "Repeated negative evidence."
                    ),
                    "source_theme": (
                        "service_quality"
                    ),
                    "evidence_refs": [
                        "review:301",
                        {
                            "reference": (
                                "review:302"
                            )
                        },
                        {
                            "id": "review:303"
                        },
                        "review:301",
                        {
                            "unknown": "ignored"
                        },
                    ],
                    "claim_strength": "validated",
                    "should_feed_strategy_agent": True,
                    "manual_review_only": False,
                }
            ],
            "opportunities": [],
            "threats": [],
        },
    )

    item = result.items[0]

    assert item.evidence_references == (
        "review:301",
        "review:302",
        "review:303",
    )

    assert (
        item.should_feed_strategy_agent
    )


def test_missing_item_id_gets_deterministic_adapter_id():
    """Missing IDs should be generated and explicitly marked."""

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="1.0",
        swot_report={
            "strengths": [],
            "weaknesses": [
                {
                    "title": (
                        "Inconsistent publishing activity"
                    ),
                    "reasoning": (
                        "Publishing cadence varied."
                    ),
                }
            ],
            "opportunities": [],
            "threats": [],
        },
    )

    item = result.items[0]

    assert item.item_id == (
        "legacy:weakness:1"
    )

    assert item.item_id_was_generated

    assert any(
        "no item_id" in warning
        for warning
        in item.normalization_warnings
    )


def test_invalid_items_are_ignored_with_warning():
    """Empty or malformed legacy items should not become claims."""

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="1.0",
        swot_report={
            "strengths": [
                {},
                {
                    "item_id": "S_999",
                    "title": "   ",
                },
            ],
            "weaknesses": "invalid",
            "opportunities": [],
            "threats": [],
        },
    )

    assert result.items == ()

    assert len(result.warnings) == 3

    assert any(
        "strengths" in warning
        for warning in result.warnings
    )

    assert any(
        "weaknesses" in warning
        for warning in result.warnings
    )


def test_baseline_metadata_and_source_coverage_are_preserved():
    """The baseline should retain IDs, version, and source coverage."""

    result = normalize_legacy_swot(
        business_id=_BUSINESS_ID,
        report_id=_REPORT_ID,
        engine_version="1.0",
        swot_report={
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
            "business_profile",
        ),
    )

    assert result.business_id == _BUSINESS_ID

    assert result.report_id == _REPORT_ID

    assert result.engine_version == "1.0"

    assert result.source_coverage == (
        "business_profile",
        "google_maps_reviews",
    )

    assert result.items == ()