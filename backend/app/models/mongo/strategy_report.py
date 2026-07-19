"""
Strategy Report MongoDB Document

Stores the complete grounded Strategy Agent output and preserves
lineage to the approved SWOT report used as its only source.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


class StrategyReportDocument(Document):
    """Persisted grounded Strategy output."""

    report_id: UUID = Field(
        default_factory=uuid4,
    )

    business_id: UUID = Indexed()

    source_swot_id: UUID

    source_proposal_id: UUID | None = None

    engine_version: str = "2.0"

    business_type: str = "unknown"

    strategic_posture: str = "balanced"

    posture_rationale: str = ""

    positioning: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    audience: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    value_proposition: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    tone_of_voice: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    content_pillars: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    channels: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    goals: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    tows_matrix: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    priority_action_plan: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    resource_assessment: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    campaign_brief_feed: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    strategy_quality_report: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    meta: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        ),
    )

    class Settings:
        name = "strategy_reports"

        indexes = [
            IndexModel(
                [
                    (
                        "business_id",
                        ASCENDING,
                    ),
                    (
                        "created_at",
                        DESCENDING,
                    ),
                ]
            ),
            IndexModel(
                [
                    (
                        "business_id",
                        ASCENDING,
                    ),
                    (
                        "source_swot_id",
                        ASCENDING,
                    ),
                ]
            ),
        ]

    def __repr__(self) -> str:
        return (
            "<StrategyReport "
            f"report={self.report_id} "
            f"business={self.business_id} "
            f"source_swot={self.source_swot_id}>"
        )