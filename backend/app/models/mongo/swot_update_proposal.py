"""
SWOT Update Proposal MongoDB Document

Stores one tenant-scoped draft SWOT update proposal.

The document preserves the normalized baseline snapshot and the
deterministic proposal output required to apply later approval
decisions safely.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


ProposalPersistenceStatus = Literal[
    "draft",
    "approved",
    "rejected",
    "superseded",
]


class SwotUpdateProposalDocument(Document):
    """Persisted draft update proposal for one business."""

    proposal_id: UUID = Indexed(
        unique=True,
    )

    business_id: UUID = Indexed()

    proposal_mode: str = "update"

    base_report_id: UUID | None = None

    base_engine_version: str | None = None

    proposal_version: str = "1.0"

    status: ProposalPersistenceStatus = (
        "draft"
    )

    baseline_snapshot: dict[
        str,
        Any,
    ] | None = None

    candidate_snapshot: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    proposal_snapshot: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    generation_metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    source_coverage: list[str] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )

    requires_human_approval: bool = True

    approval_decisions: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    approved_report_id: UUID | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        ),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        ),
    )

    class Settings:
        name = "swot_update_proposals"

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
                ]
            ),
            IndexModel(
                [
                    (
                        "business_id",
                        ASCENDING,
                    ),
                    (
                        "base_report_id",
                        ASCENDING,
                    ),
                ]
            ),
        ]

    def __repr__(self) -> str:
        return (
            "<SwotUpdateProposal "
            f"proposal={self.proposal_id} "
            f"business={self.business_id} "
            f"status={self.status}>"
        )