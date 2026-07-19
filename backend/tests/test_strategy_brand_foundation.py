"""
Strategy Brand Foundation Tests
"""

from app.agents.strategy.post_processor.brand_foundation import (
    build_brand_strategy_foundation,
)
from app.agents.strategy.schemas.output import (
    StrategyOutput,
)


def _parsed_output() -> dict:
    """Build one grounded LLM strategy response."""

    return {
        "positioning": {
            "statement": (
                "A service-focused cafe."
            ),
            "category_focus": (
                "Reliable customer experience"
            ),
            "differentiators": [
                "Responsive service improvement"
            ],
            "reasoning": (
                "Service speed is the highest "
                "priority improvement area."
            ),
            "source_swot_item_ids": [
                "W_001"
            ],
        },
        "audience": [
            {
                "segment_name": (
                    "Service-sensitive customers"
                ),
                "description": (
                    "Customers who value reliable "
                    "and timely service."
                ),
                "needs": [
                    "Predictable waiting times"
                ],
                "pain_points": [
                    "Slow service"
                ],
                "message_focus": (
                    "Clear service improvements"
                ),
                "priority": "primary",
                "source_swot_item_ids": [
                    "W_001"
                ],
            }
        ],
        "value_proposition": {
            "statement": (
                "A more responsive cafe experience."
            ),
            "customer_value": [
                "More predictable service"
            ],
            "reasons_to_believe": [
                "Service improvements are prioritized"
            ],
            "source_swot_item_ids": [
                "W_001"
            ],
        },
        "tone_of_voice": {
            "traits": [
                "clear",
                "helpful",
                "credible",
            ],
            "do": [
                "Communicate improvements directly"
            ],
            "avoid": [
                "Unsupported superiority claims"
            ],
            "rationale": (
                "The strategy requires transparent "
                "service communication."
            ),
            "source_swot_item_ids": [
                "W_001"
            ],
        },
        "content_pillars": [
            {
                "name": "Service improvement",
                "purpose": (
                    "Show operational progress."
                ),
                "key_messages": [
                    "Customer feedback drives change"
                ],
                "recommended_formats": [
                    "customer update"
                ],
                "source_swot_item_ids": [
                    "W_001"
                ],
            }
        ],
        "channels": [
            {
                "channel": "instagram",
                "role": (
                    "Communicate service updates."
                ),
                "content_focus": [
                    "Operational improvements"
                ],
                "priority": "primary",
                "reasoning": (
                    "Instagram is represented in "
                    "the approved source context."
                ),
                "source_swot_item_ids": [
                    "W_001"
                ],
            }
        ],
        "goals": [
            {
                "goal": (
                    "Improve perceived service "
                    "responsiveness."
                ),
                "goal_type": (
                    "customer_experience"
                ),
                "priority": "high",
                "success_signals": [
                    (
                        "Lower frequency of "
                        "service-speed complaints"
                    )
                ],
                "horizon": "short_term",
                "source_swot_item_ids": [
                    "W_001"
                ],
            }
        ],
    }


def test_builds_all_seven_grounded_sections():
    """All supported brand-strategy sections should survive."""

    foundation = (
        build_brand_strategy_foundation(
            _parsed_output(),
            {
                "W_001",
            },
        )
    )

    assert foundation.positioning.statement

    assert len(
        foundation.audience
    ) == 1

    assert (
        foundation
        .value_proposition
        .statement
    )

    assert foundation.tone_of_voice.traits

    assert len(
        foundation.content_pillars
    ) == 1

    assert len(
        foundation.channels
    ) == 1

    assert len(
        foundation.goals
    ) == 1


def test_unknown_source_ids_are_removed():
    """Unsupported strategic entries must fail closed."""

    parsed = _parsed_output()

    parsed["audience"][0][
        "source_swot_item_ids"
    ] = [
        "invented:item"
    ]

    foundation = (
        build_brand_strategy_foundation(
            parsed,
            {
                "W_001",
            },
        )
    )

    assert foundation.audience == []


def test_mixed_source_ids_keep_only_valid_ids():
    """Known IDs may survive while invented IDs are removed."""

    parsed = _parsed_output()

    parsed["goals"][0][
        "source_swot_item_ids"
    ] = [
        "invented:item",
        "W_001",
        "W_001",
    ]

    foundation = (
        build_brand_strategy_foundation(
            parsed,
            {
                "W_001",
            },
        )
    )

    assert (
        foundation
        .goals[0]
        .source_swot_item_ids
        == [
            "W_001"
        ]
    )


def test_unsupported_positioning_becomes_empty():
    """A singular section without valid grounding is cleared."""

    parsed = _parsed_output()

    parsed["positioning"][
        "source_swot_item_ids"
    ] = [
        "invented:item"
    ]

    foundation = (
        build_brand_strategy_foundation(
            parsed,
            {
                "W_001",
            },
        )
    )

    assert (
        foundation.positioning.statement
        == ""
    )

    assert (
        foundation
        .positioning
        .source_swot_item_ids
        == []
    )


def test_strategy_output_exposes_brand_foundation():
    """The public Strategy output should contain all new fields."""

    foundation = (
        build_brand_strategy_foundation(
            _parsed_output(),
            {
                "W_001",
            },
        )
    )

    output = StrategyOutput(
        business_type="cafe",
        positioning=(
            foundation.positioning
        ),
        audience=foundation.audience,
        value_proposition=(
            foundation.value_proposition
        ),
        tone_of_voice=(
            foundation.tone_of_voice
        ),
        content_pillars=(
            foundation.content_pillars
        ),
        channels=foundation.channels,
        goals=foundation.goals,
    )

    dumped = output.model_dump()

    assert "positioning" in dumped

    assert "audience" in dumped

    assert "value_proposition" in dumped

    assert "tone_of_voice" in dumped

    assert "content_pillars" in dumped

    assert "channels" in dumped

    assert "goals" in dumped