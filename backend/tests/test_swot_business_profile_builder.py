"""
SWOT Business Profile Builder Tests
"""

from app.services.swot_business_profile_builder import (
    build_swot_business_profile,
)


def test_preserves_theme_extractor_frequency_and_sentiment():
    """
    Theme Extractor output must reach SWOT v7 without falling back
    to frequency=1 or a fabricated positive sentiment.
    """

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
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
                    "frequency_count": 200,
                    "sentiment_distribution": {
                        "positive": 40,
                        "negative": 145,
                        "neutral": 10,
                        "mixed": 5,
                    },
                    "mentions": [
                        f"google_maps:review:{index}"
                        for index in range(
                            200
                        )
                    ],
                }
            ],
        },
        target_review_count=200,
    )

    assert len(profile.themes) == 1

    theme = profile.themes[0]

    assert theme.theme_category == (
        "service_speed"
    )

    assert theme.frequency == 200

    assert (
        theme.sentiment_balance.positive
        == 40
    )

    assert (
        theme.sentiment_balance.negative
        == 145
    )

    assert (
        theme.sentiment_balance.neutral
        == 10
    )

    assert (
        theme.sentiment_balance.mixed
        == 5
    )

    assert (
        theme.sentiment_balance.total
        == 200
    )

    assert (
        profile
        .reviews_summary
        .target_review_count
        == 200
    )


def test_mentions_become_evidence_references():
    """
    Theme mentions should remain traceable evidence references.
    """

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "product_quality"
                    ),
                    "entity_type": (
                        "target_business"
                    ),
                    "frequency_count": 3,
                    "sentiment_distribution": {
                        "positive": 3,
                        "negative": 0,
                        "neutral": 0,
                        "mixed": 0,
                    },
                    "mentions": [
                        "google_maps:review:1",
                        "facebook:comment:2",
                        "instagram:comment:3",
                    ],
                }
            ],
        },
    )

    theme = profile.themes[0]

    assert theme.evidence_refs == [
        "google_maps:review:1",
        "facebook:comment:2",
        "instagram:comment:3",
    ]


def test_explicit_evidence_references_take_priority():
    """Explicit evidence references should be preserved and deduplicated."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "service_quality"
                    ),
                    "frequency_count": 2,
                    "sentiment_distribution": {
                        "positive": 2,
                    },
                    "mentions": [
                        "internal:mention:1",
                    ],
                    "evidence_refs": [
                        "google_maps:review:10",
                        "google_maps:review:10",
                        "instagram:comment:11",
                    ],
                }
            ],
        },
    )

    assert (
        profile.themes[0].evidence_refs
        == [
            "google_maps:review:10",
            "instagram:comment:11",
        ]
    )


def test_preserves_extracted_signal_collections():
    """All deterministic signal collections should reach SWOT v7."""

    positive_signal = {
        "theme_category": "product_quality",
        "reason": "high_positive_sentiment",
    }

    negative_signal = {
        "theme_category": "service_speed",
        "reason": "high_negative_sentiment",
    }

    opportunity_signal = {
        "theme_category": "menu_variety",
        "reason": "overperforms_competitors",
    }

    threat_signal = {
        "theme_category": "pricing",
        "reason": "underperforms_competitors",
    }

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [],
            "positive_signals": [
                positive_signal
            ],
            "negative_signals": [
                negative_signal
            ],
            "opportunity_signals": [
                opportunity_signal
            ],
            "threat_signals": [
                threat_signal
            ],
            "comparison_summary": {
                "target_business_overperforms": [
                    "menu_variety"
                ],
                "target_business_underperforms": [
                    "pricing"
                ],
                "parity_areas": [],
            },
        },
    )

    assert profile.positive_signals == [
        positive_signal
    ]

    assert profile.negative_signals == [
        negative_signal
    ]

    assert profile.opportunity_signals == [
        opportunity_signal
    ]

    assert profile.threat_signals == [
        threat_signal
    ]

    assert (
        profile.comparison_summary[
            "target_business_overperforms"
        ]
        == [
            "menu_variety"
        ]
    )


def test_supports_legacy_theme_field_names():
    """Older fixtures should remain compatible with the builder."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "cleanliness"
                    ),
                    "frequency": 8,
                    "sentiment_balance": {
                        "positive": 6,
                        "negative": 1,
                        "neutral": 1,
                        "mixed": 0,
                    },
                    "mentions": [
                        "legacy:1",
                        "legacy:2",
                    ],
                }
            ],
        },
    )

    theme = profile.themes[0]

    assert theme.frequency == 8

    assert (
        theme.sentiment_balance.positive
        == 6
    )

    assert (
        theme.sentiment_balance.negative
        == 1
    )


def test_missing_frequency_uses_explicit_mention_count():
    """Missing frequency should fall back to observed mentions."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "staff_behavior"
                    ),
                    "sentiment_distribution": {
                        "positive": 2,
                        "negative": 1,
                    },
                    "mentions": [
                        "review:1",
                        "review:2",
                        "review:3",
                    ],
                }
            ],
        },
    )

    assert (
        profile.themes[0].frequency
        == 3
    )


def test_invalid_theme_without_category_is_ignored():
    """A malformed Theme Extractor row must not enter SWOT v7."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {},
                {
                    "frequency_count": 10,
                    "sentiment_distribution": {
                        "positive": 10,
                    },
                },
            ],
        },
    )

    assert profile.themes == []
def test_preserves_confidence_quotes_and_cross_source_platforms():
    """
    Theme enrichment should survive the bridge into SWOT v7.
    """

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
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
                        "Service was slow.",
                        "The order took too long.",
                        "Waiting time needs improvement.",
                    ],
                }
            ],
        },
        target_review_count=3,
    )

    theme = profile.themes[0]

    assert theme.confidence_score == 0.91

    assert theme.representative_quotes == [
        "Service was slow.",
        "The order took too long.",
        "Waiting time needs improvement.",
    ]

    assert theme.source_platforms == [
        "google_maps",
        "facebook",
        "instagram",
    ]

    assert theme.evidence_refs == [
        "google_maps:review:g-1",
        "facebook:comment:f-1",
        "instagram:comment:i-1",
    ]


def test_explicit_source_platforms_are_preserved_and_deduplicated():
    """Explicit and derived source platforms should be merged safely."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "product_quality"
                    ),
                    "frequency_count": 2,
                    "sentiment_distribution": {
                        "positive": 2,
                    },
                    "source_platforms": [
                        "instagram",
                        "instagram",
                        "unknown",
                    ],
                    "evidence_refs": [
                        "google_maps:review:g-1",
                        "instagram:comment:i-1",
                    ],
                }
            ],
        },
    )

    assert (
        profile.themes[0]
        .source_platforms
        == [
            "instagram",
            "google_maps",
        ]
    )


def test_confidence_is_clamped_to_public_range():
    """Invalid high confidence must not escape the profile contract."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "cleanliness"
                    ),
                    "frequency_count": 2,
                    "confidence_score": 1.8,
                    "sentiment_distribution": {
                        "positive": 2,
                    },
                    "mentions": [
                        "google_maps:review:1",
                        "google_maps:review:2",
                    ],
                }
            ],
        },
    )

    assert (
        profile.themes[0]
        .confidence_score
        == 1.0
    )


def test_quote_objects_are_normalized_to_text():
    """Legacy quote objects should become plain representative text."""

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "staff_behavior"
                    ),
                    "frequency_count": 2,
                    "sentiment_distribution": {
                        "positive": 2,
                    },
                    "representative_quotes": [
                        {
                            "text": (
                                "The staff were friendly."
                            ),
                            "sentiment": "positive",
                        },
                        {
                            "text": (
                                "The staff were friendly."
                            ),
                        },
                        {
                            "text": (
                                "Helpful service."
                            ),
                        },
                    ],
                }
            ],
        },
    )

    assert (
        profile.themes[0]
        .representative_quotes
        == [
            "The staff were friendly.",
            "Helpful service.",
        ]
    )


def test_fallback_review_count_uses_unique_evidence_not_theme_sum():
    """
    One review supporting multiple themes must be counted once.
    """

    profile = build_swot_business_profile(
        business_name="Example Cafe",
        business_type="cafe",
        themes_output={
            "themes": [
                {
                    "theme_category": (
                        "service_speed"
                    ),
                    "frequency_count": 2,
                    "sentiment_distribution": {
                        "negative": 2,
                    },
                    "mentions": [
                        "google_maps:review:1",
                        "facebook:comment:2",
                    ],
                },
                {
                    "theme_category": (
                        "staff_behavior"
                    ),
                    "frequency_count": 2,
                    "sentiment_distribution": {
                        "positive": 2,
                    },
                    "mentions": [
                        "google_maps:review:1",
                        "instagram:comment:3",
                    ],
                },
            ],
        },
    )

    assert (
        profile
        .reviews_summary
        .target_review_count
        == 3
    )

def test_preserves_manual_review_flag():
    """
    An unverified theme must retain its manual-review flag
    when mapped into the SWOT v7 profile.
    """

    profile = build_swot_business_profile(
        business_name="Starbucks",
        business_type="coffee_shop",
        themes_output={
            "themes": [
                {
                    "theme_name": (
                        "Product Safety Concern"
                    ),
                    "theme_category": (
                        "product_safety"
                    ),
                    "entity_type": (
                        "target_business"
                    ),
                    "frequency_count": 1,
                    "sentiment_distribution": {
                        "positive": 0,
                        "negative": 1,
                        "neutral": 0,
                        "mixed": 0,
                    },
                    "confidence_score": 0.95,
                    "requires_manual_review": True,
                    "mentions": [
                        "instagram:comment:safety-1",
                    ],
                    "representative_quotes": [
                        (
                            "An unverified customer "
                            "safety concern."
                        ),
                    ],
                }
            ],
        },
        target_review_count=1,
    )

    assert len(profile.themes) == 1

    theme = profile.themes[0]

    assert (
        theme.theme_category
        == "product_safety"
    )

    assert (
        theme.requires_manual_review
        is True
    )

    assert theme.evidence_refs == [
        "instagram:comment:safety-1",
    ]