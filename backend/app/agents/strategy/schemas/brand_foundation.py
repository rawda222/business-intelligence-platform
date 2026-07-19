"""
Strategy Agent v2 - Brand Foundation Schemas

Defines evidence-grounded brand strategy outputs derived only from
approved SWOT items.

Every strategic section carries source_swot_item_ids so Python can
verify that the generated recommendation is anchored in approved
SWOT evidence.
"""

from typing import List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class PositioningStrategy(BaseModel):
    """Evidence-grounded market positioning."""

    model_config = ConfigDict(
        extra="ignore",
    )

    statement: str = ""

    category_focus: str = ""

    differentiators: List[str] = Field(
        default_factory=list,
    )

    reasoning: str = ""

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class AudienceSegment(BaseModel):
    """One evidence-grounded audience segment."""

    model_config = ConfigDict(
        extra="ignore",
    )

    segment_name: str = ""

    description: str = ""

    needs: List[str] = Field(
        default_factory=list,
    )

    pain_points: List[str] = Field(
        default_factory=list,
    )

    message_focus: str = ""

    priority: str = "secondary"

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class ValuePropositionStrategy(BaseModel):
    """Evidence-grounded customer value proposition."""

    model_config = ConfigDict(
        extra="ignore",
    )

    statement: str = ""

    customer_value: List[str] = Field(
        default_factory=list,
    )

    reasons_to_believe: List[str] = Field(
        default_factory=list,
    )

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class ToneOfVoiceStrategy(BaseModel):
    """Recommended brand voice derived from approved strategy."""

    model_config = ConfigDict(
        extra="ignore",
    )

    traits: List[str] = Field(
        default_factory=list,
    )

    do: List[str] = Field(
        default_factory=list,
    )

    avoid: List[str] = Field(
        default_factory=list,
    )

    rationale: str = ""

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class ContentPillarStrategy(BaseModel):
    """One grounded strategic content pillar."""

    model_config = ConfigDict(
        extra="ignore",
    )

    name: str = ""

    purpose: str = ""

    key_messages: List[str] = Field(
        default_factory=list,
    )

    recommended_formats: List[str] = Field(
        default_factory=list,
    )

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class ChannelStrategy(BaseModel):
    """One recommended strategic channel."""

    model_config = ConfigDict(
        extra="ignore",
    )

    channel: str = ""

    role: str = ""

    content_focus: List[str] = Field(
        default_factory=list,
    )

    priority: str = "secondary"

    reasoning: str = ""

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class StrategyGoal(BaseModel):
    """One grounded strategic goal."""

    model_config = ConfigDict(
        extra="ignore",
    )

    goal: str = ""

    goal_type: str = ""

    priority: str = "medium"

    success_signals: List[str] = Field(
        default_factory=list,
    )

    horizon: str = "short_term"

    source_swot_item_ids: List[str] = Field(
        default_factory=list,
    )


class BrandStrategyFoundation(BaseModel):
    """Complete brand strategy foundation."""

    model_config = ConfigDict(
        extra="ignore",
    )

    positioning: PositioningStrategy = Field(
        default_factory=PositioningStrategy,
    )

    audience: List[AudienceSegment] = Field(
        default_factory=list,
    )

    value_proposition: (
        ValuePropositionStrategy
    ) = Field(
        default_factory=(
            ValuePropositionStrategy
        ),
    )

    tone_of_voice: ToneOfVoiceStrategy = Field(
        default_factory=ToneOfVoiceStrategy,
    )

    content_pillars: List[
        ContentPillarStrategy
    ] = Field(
        default_factory=list,
    )

    channels: List[ChannelStrategy] = Field(
        default_factory=list,
    )

    goals: List[StrategyGoal] = Field(
        default_factory=list,
    )