"""
SWOT and Strategy Persistence Service

Persists draft proposals, approved SWOT reports, and grounded
Strategy outputs while preserving tenant and source lineage.

All reads require business_id together with the resource identity.
"""

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.models.mongo.strategy_report import (
    StrategyReportDocument,
)
from app.models.mongo.swot_report import (
    SWOTReportDocument,
)
from app.models.mongo.swot_update_proposal import (
    SwotUpdateProposalDocument,
)


def _serialize(
    value: Any,
) -> Any:
    """Convert supported domain values to Mongo-safe containers."""

    if isinstance(
        value,
        Enum,
    ):
        return _serialize(
            value.value
        )

    if isinstance(
        value,
        UUID,
    ):
        return str(
            value
        )

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=UTC
            )

        return value.astimezone(
            UTC
        )

    if is_dataclass(
        value
    ):
        return _serialize(
            asdict(
                value
            )
        )

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(
        model_dump
    ):
        return _serialize(
            model_dump(
                mode="python"
            )
        )

    if isinstance(
        value,
        dict,
    ):
        return {
            str(
                key
            ): _serialize(
                nested_value
            )
            for key, nested_value
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _serialize(
                nested_value
            )
            for nested_value
            in value
        ]

    return value


def _uuid(
    value: Any,
    *,
    field_name: str,
) -> UUID:
    """Normalize one UUID value or fail closed."""

    if isinstance(
        value,
        UUID,
    ):
        return value

    try:
        return UUID(
            str(
                value
            )
        )
    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as error:
        raise ValueError(
            f"{field_name} must be a valid UUID."
        ) from error


async def save_swot_update_proposal(
    *,
    baseline: Any,
    generation: Any,
    grounded_result: Any,
) -> SwotUpdateProposalDocument:
    """Persist one deterministic draft SWOT update proposal."""

    proposal = grounded_result.proposal

    document = SwotUpdateProposalDocument(
        proposal_id=_uuid(
            proposal.proposal_id,
            field_name="proposal_id",
        ),

        business_id=_uuid(
            proposal.business_id,
            field_name="business_id",
        ),

        base_report_id=(
            _uuid(
                proposal.base_report_id,
                field_name="base_report_id",
            )
            if proposal.base_report_id is not None
            else None
        ),

        proposal_mode=proposal.proposal_mode,

        base_engine_version=(
            proposal.base_engine_version
        ),

        proposal_version=(
            proposal.proposal_version
        ),

        status="draft",

        baseline_snapshot=(
            _serialize(
                baseline
            )
            if baseline is not None
            else None
        ),

        candidate_snapshot=(
            _serialize(
                grounded_result.candidates
            )
        ),

        proposal_snapshot=(
            _serialize(
                proposal
            )
        ),

        generation_metadata={
            "provider_used": getattr(
                generation,
                "provider_used",
                "unknown",
            ),

            "model_used": getattr(
                generation,
                "model_used",
                "unknown",
            ),

            "fallback_used": bool(
                getattr(
                    generation,
                    "fallback_used",
                    False,
                )
            ),

            "raw_item_count": getattr(
                generation,
                "raw_item_count",
                0,
            ),

            "accepted_item_count": getattr(
                generation,
                "accepted_item_count",
                0,
            ),

            "blocked_item_count": getattr(
                generation,
                "blocked_item_count",
                0,
            ),

            "safe_for_update_proposal": bool(
                getattr(
                    generation,
                    "safe_for_update_proposal",
                    False,
                )
            ),
        },

        source_coverage=list(
            proposal.current_sources
        ),

        warnings=list(
            grounded_result.warnings
        ),

        requires_human_approval=(
            proposal.requires_human_approval
        ),
    )

    await document.insert()

    return document


async def get_swot_update_proposal(
    *,
    business_id: UUID,
    proposal_id: UUID,
) -> SwotUpdateProposalDocument | None:
    """Load one proposal without crossing tenant boundaries."""

    return await (
        SwotUpdateProposalDocument
        .find_one(
            (
                SwotUpdateProposalDocument
                .business_id
                == business_id
            ),
            (
                SwotUpdateProposalDocument
                .proposal_id
                == proposal_id
            ),
        )
    )


async def mark_proposal_approved(
    *,
    document: SwotUpdateProposalDocument,
    decisions: tuple[Any, ...],
    approved_report_id: UUID,
) -> SwotUpdateProposalDocument:
    """Mark a persisted draft proposal as approved."""

    if document.status != "draft":
        raise ValueError(
            "Only draft SWOT proposals may be approved."
        )

    document.status = "approved"

    document.approval_decisions = (
        _serialize(
            decisions
        )
    )

    document.approved_report_id = (
        approved_report_id
    )

    document.updated_at = datetime.now(
        UTC
    )

    await document.save()

    return document


def _approved_swot_report_payload(
    approved: Any,
) -> dict[str, Any]:
    """Group approved items by SWOT quadrant."""

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
    }

    quadrant_keys = {
        "strength": "strengths",
        "strengths": "strengths",
        "weakness": "weaknesses",
        "weaknesses": "weaknesses",
        "opportunity": "opportunities",
        "opportunities": "opportunities",
        "threat": "threats",
        "threats": "threats",
    }

    for item in approved.items:
        key = quadrant_keys.get(
            str(
                item.quadrant
            ).strip().lower()
        )

        if key is None:
            raise ValueError(
                "Approved SWOT item has an "
                "unsupported quadrant."
            )

        grouped[key].append(
            _serialize(
                item
            )
        )

    return grouped


async def save_approved_swot_report(
    *,
    approved: Any,
    business_type: str,
) -> SWOTReportDocument:
    """Persist one approved SWOT report as engine version 8."""

    if not approved.approval_complete:
        raise ValueError(
            "Approved SWOT decisions are incomplete."
        )

    if approved.unresolved_candidate_ids:
        raise ValueError(
            "Approved SWOT contains unresolved candidates."
        )

    document = SWOTReportDocument(
        report_id=_uuid(
            approved.approved_report_id,
            field_name="approved_report_id",
        ),
        business_id=_uuid(
            approved.business_id,
            field_name="business_id",
        ),
        engine_version=(
            approved.output_engine_version
        ),
        business_type=(
            business_type
        ),
        status="approved",
        base_report_id=(
    _uuid(
        approved.base_report_id,
        field_name="base_report_id",
    )
    if approved.base_report_id is not None
    else None
),
        source_proposal_id=_uuid(
            approved.source_proposal_id,
            field_name="source_proposal_id",
        ),
        approval_complete=(
            approved.approval_complete
        ),
        ready_for_strategy=(
            approved.ready_for_strategy
        ),
        approved_candidate_ids=list(
            approved.approved_candidate_ids
        ),
        rejected_candidate_ids=list(
            approved.rejected_candidate_ids
        ),
        unresolved_candidate_ids=list(
            approved.unresolved_candidate_ids
        ),
        source_coverage=list(
            approved.source_coverage
        ),
        swot_report=(
            _approved_swot_report_payload(
                approved
            )
        ),
        validation_results={
            "overall_status": "PASS",
            "violations": [],
        },
        meta={
            "base_engine_version": (
                approved.base_engine_version
            ),
            "output_engine_version": (
                approved.output_engine_version
            ),
            "source_proposal_id": str(
                approved.source_proposal_id
            ),
            "approval_complete": (
                approved.approval_complete
            ),
            "ready_for_strategy": (
                approved.ready_for_strategy
            ),
            "version": (
                approved.version
            ),
            "warnings": list(
                approved.warnings
            ),
        },
    )

    await document.insert()

    return document


async def get_latest_approved_swot_report(
    *,
    business_id: UUID,
) -> SWOTReportDocument | None:
    """Load the latest approved and Strategy-ready SWOT report."""

    return await SWOTReportDocument.find_one(
        (
            SWOTReportDocument
            .business_id
            == business_id
        ),
        SWOTReportDocument.status
        == "approved",
        (
            SWOTReportDocument
            .approval_complete
            == True  # noqa: E712
        ),
        (
            SWOTReportDocument
            .ready_for_strategy
            == True  # noqa: E712
        ),
        sort=[
            (
                "created_at",
                -1,
            )
        ],
    )


async def save_strategy_report(
    *,
    business_id: UUID,
    approved_swot: SWOTReportDocument,
    strategy_output: Any,
) -> StrategyReportDocument:
    """Persist the complete Strategy Agent output."""

    if (
        approved_swot.business_id
        != business_id
    ):
        raise ValueError(
            "Approved SWOT business_id does not "
            "match the requested business_id."
        )

    if (
        approved_swot.status
        != "approved"
        or not approved_swot.approval_complete
        or not approved_swot.ready_for_strategy
    ):
        raise ValueError(
            "Strategy requires an approved and "
            "Strategy-ready SWOT report."
        )

    payload = _serialize(
        strategy_output
    )

    document = StrategyReportDocument(
        business_id=business_id,
        source_swot_id=(
            approved_swot.report_id
        ),
        source_proposal_id=(
            approved_swot
            .source_proposal_id
        ),
        engine_version=str(
            payload.get(
                "engine_version",
                "2.0",
            )
        ),
        business_type=str(
            payload.get(
                "business_type",
                approved_swot.business_type,
            )
        ),
        strategic_posture=str(
            payload.get(
                "strategic_posture",
                "balanced",
            )
        ),
        posture_rationale=str(
            payload.get(
                "posture_rationale",
                "",
            )
        ),
        positioning=dict(
            payload.get(
                "positioning",
                {},
            )
        ),
        audience=list(
            payload.get(
                "audience",
                [],
            )
        ),
        value_proposition=dict(
            payload.get(
                "value_proposition",
                {},
            )
        ),
        tone_of_voice=dict(
            payload.get(
                "tone_of_voice",
                {},
            )
        ),
        content_pillars=list(
            payload.get(
                "content_pillars",
                [],
            )
        ),
        channels=list(
            payload.get(
                "channels",
                [],
            )
        ),
        goals=list(
            payload.get(
                "goals",
                [],
            )
        ),
        tows_matrix=dict(
            payload.get(
                "tows_matrix",
                {},
            )
        ),
        priority_action_plan=list(
            payload.get(
                "priority_action_plan",
                [],
            )
        ),
        resource_assessment=list(
            payload.get(
                "resource_assessment",
                [],
            )
        ),
        campaign_brief_feed=list(
            payload.get(
                "campaign_brief_feed",
                [],
            )
        ),
        strategy_quality_report=dict(
            payload.get(
                "strategy_quality_report",
                {},
            )
        ),
        meta=dict(
            payload.get(
                "meta",
                {},
            )
        ),
    )

    await document.insert()

    return document


async def get_latest_strategy_report(
    *,
    business_id: UUID,
) -> StrategyReportDocument | None:
    """Load the latest persisted Strategy report for one tenant."""

    return await StrategyReportDocument.find_one(
        (
            StrategyReportDocument
            .business_id
            == business_id
        ),
        sort=[
            (
                "created_at",
                -1,
            )
        ],
    )