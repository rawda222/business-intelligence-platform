"""
SWOT and Strategy Persistence Model Contract Tests

These tests inspect Beanie/Pydantic field contracts without requiring
an initialized MongoDB collection.
"""

from app.models.mongo.strategy_report import (
    StrategyReportDocument,
)
from app.models.mongo.swot_report import (
    SWOTReportDocument,
)
from app.models.mongo.swot_update_proposal import (
    SwotUpdateProposalDocument,
)


def _field_names(
    model_type,
) -> set[str]:
    """Return the public Pydantic field names."""

    return set(
        model_type.model_fields
    )


def test_proposal_document_exposes_required_lineage():
    """Proposal persistence should expose tenant and baseline lineage."""

    fields = _field_names(
        SwotUpdateProposalDocument
    )

    assert {
        "proposal_id",
        "business_id",
        "base_report_id",
        "base_engine_version",
        "status",
        "baseline_snapshot",
        "candidate_snapshot",
        "proposal_snapshot",
        "generation_metadata",
        "source_coverage",
        "warnings",
        "requires_human_approval",
        "approval_decisions",
        "approved_report_id",
        "created_at",
        "updated_at",
    }.issubset(fields)

    assert (
        SwotUpdateProposalDocument
        .model_fields["status"]
        .default
        == "draft"
    )

    assert (
        SwotUpdateProposalDocument
        .model_fields[
            "requires_human_approval"
        ]
        .default
        is True
    )


def test_swot_document_exposes_approval_and_strategy_gates():
    """Approved SWOT persistence should expose explicit safety gates."""

    fields = _field_names(
        SWOTReportDocument
    )

    assert {
        "report_id",
        "business_id",
        "engine_version",
        "business_type",
        "status",
        "base_report_id",
        "source_proposal_id",
        "approval_complete",
        "ready_for_strategy",
        "approved_candidate_ids",
        "rejected_candidate_ids",
        "unresolved_candidate_ids",
        "source_coverage",
        "swot_report",
        "validation_results",
        "meta",
        "created_at",
    }.issubset(fields)

    assert (
        SWOTReportDocument
        .model_fields["status"]
        .default
        == "generated"
    )

    assert (
        SWOTReportDocument
        .model_fields[
            "approval_complete"
        ]
        .default
        is False
    )

    assert (
        SWOTReportDocument
        .model_fields[
            "ready_for_strategy"
        ]
        .default
        is False
    )


def test_strategy_document_exposes_brand_foundation():
    """Strategy persistence should expose the complete output contract."""

    fields = _field_names(
        StrategyReportDocument
    )

    assert {
        "report_id",
        "business_id",
        "source_swot_id",
        "source_proposal_id",
        "engine_version",
        "business_type",
        "strategic_posture",
        "posture_rationale",
        "positioning",
        "audience",
        "value_proposition",
        "tone_of_voice",
        "content_pillars",
        "channels",
        "goals",
        "tows_matrix",
        "priority_action_plan",
        "resource_assessment",
        "campaign_brief_feed",
        "strategy_quality_report",
        "meta",
        "created_at",
    }.issubset(fields)

    assert (
        StrategyReportDocument
        .model_fields[
            "engine_version"
        ]
        .default
        == "2.0"
    )