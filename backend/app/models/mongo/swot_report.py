"""
SWOT Report Document Model

Stores complete SWOT analysis reports in MongoDB.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from beanie import Document, Indexed
from pydantic import Field
from pymongo import (
    ASCENDING,
    DESCENDING,
    IndexModel,
)


SwotReportStatus = Literal[
    "generated",
    "approved",
    "superseded",
]


class SWOTReportDocument(Document):
    """
    SWOT report document stored in MongoDB.

    Contains the complete output from the SWOT Agent:

    - Strengths
    - Weaknesses
    - Opportunities
    - Threats
    - Watchouts
    - Strategic summary
    - Quality report
    - Validation results
    - Approval and source lineage
    """

    # ========================================================
    # Identification
    # ========================================================
    report_id: UUID = Field(
        default_factory=uuid4,
    )

    business_id: UUID = Indexed()

    # ========================================================
    # Engine Metadata
    # ========================================================
    engine_version: str = "7.0"

    business_type: str = "unknown"

    # ========================================================
    # Approval and Lineage
    # ========================================================
    status: SwotReportStatus = "generated"

    base_report_id: UUID | None = None

    source_proposal_id: UUID | None = None

    approval_complete: bool = False

    ready_for_strategy: bool = False

    approved_candidate_ids: list[str] = Field(
        default_factory=list,
    )

    rejected_candidate_ids: list[str] = Field(
        default_factory=list,
    )

    unresolved_candidate_ids: list[str] = Field(
        default_factory=list,
    )

    source_coverage: list[str] = Field(
        default_factory=list,
    )

    # ========================================================
    # SWOT Content
    # ========================================================
    swot_report: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Main SWOT structure containing strengths, "
            "weaknesses, opportunities, and threats."
        ),
    )

    watchouts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Early warning signals.",
    )

    derived_opportunities: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    directional_competitive_signals: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    # ========================================================
    # Strategic Analysis
    # ========================================================
    strategic_summary: dict[str, Any] = Field(
        default_factory=dict,
    )

    strategic_context: dict[str, Any] = Field(
        default_factory=dict,
    )

    priority_insights: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    ambiguous_factors: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    # ========================================================
    # Matrix Outputs
    # ========================================================
    matrix_outputs: dict[str, Any] = Field(
        default_factory=dict,
    )

    # ========================================================
    # Quality and Validation
    # ========================================================
    quality_report: dict[str, Any] = Field(
        default_factory=dict,
    )

    validation_results: dict[str, Any] = Field(
        default_factory=dict,
    )

    # ========================================================
    # Execution Metadata
    # ========================================================
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "LLM provider, model, cost, processing time, "
            "and execution metadata."
        ),
    )

    # ========================================================
    # Timestamps
    # ========================================================
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        ),
    )

    # ========================================================
    # MongoDB Settings
    # ========================================================
    class Settings:
        name = "swot_reports"

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
                        "status",
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
                        "source_proposal_id",
                        ASCENDING,
                    ),
                ],
                sparse=True,
            ),
        ]

    def __repr__(self) -> str:
        return (
            "<SWOTReport "
            f"report={self.report_id} "
            f"business={self.business_id} "
            f"status={self.status} "
            f"created={self.created_at}>"
        )