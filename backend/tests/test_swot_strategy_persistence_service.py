"""
SWOT and Strategy Persistence Service Tests

Tests serialization, lineage, tenant isolation, approval gates,
and document mapping without requiring an initialized MongoDB
collection.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest

import app.services.swot_strategy_persistence_service as persistence


_BUSINESS_ID = UUID(
    "11111111-2222-3333-4444-555555555555"
)

_OTHER_BUSINESS_ID = UUID(
    "22222222-3333-4444-5555-666666666666"
)

_BASE_REPORT_ID = UUID(
    "33333333-4444-5555-6666-777777777777"
)

_PROPOSAL_ID = UUID(
    "44444444-5555-6666-7777-888888888888"
)

_APPROVED_REPORT_ID = UUID(
    "55555555-6666-7777-8888-999999999999"
)


class FakeDocument:
    """Minimal async Beanie Document replacement."""

    def __init__(
        self,
        **values,
    ):
        for key, value in values.items():
            setattr(
                self,
                key,
                value,
            )

        self.insert_called = False
        self.save_called = False

    async def insert(
        self,
    ):
        self.insert_called = True

        return self

    async def save(
        self,
    ):
        self.save_called = True

        return self


@dataclass(frozen=True, slots=True)
class FakeBaseline:
    """Minimal normalized baseline snapshot."""

    business_id: UUID

    report_id: UUID

    engine_version: str


@dataclass(frozen=True, slots=True)
class FakeCandidate:
    """Minimal candidate snapshot."""

    candidate_id: str

    business_id: UUID

    quadrant: str


@dataclass(frozen=True, slots=True)
class FakeProposal:
    """Minimal draft proposal contract."""

    proposal_id: UUID

    business_id: UUID

    base_report_id: UUID

    base_engine_version: str

    proposal_version: str

    status: str

    current_sources: tuple[str, ...]

    warnings: tuple[str, ...]

    requires_human_approval: bool


@dataclass(frozen=True, slots=True)
class FakeGeneration:
    """Minimal grounded generation metadata."""

    provider_used: str

    model_used: str

    fallback_used: bool

    raw_item_count: int

    accepted_item_count: int

    blocked_item_count: int

    safe_for_update_proposal: bool


@dataclass(frozen=True, slots=True)
class FakeGroundedResult:
    """Minimal grounded proposal result."""

    proposal: FakeProposal

    candidates: tuple[
        FakeCandidate,
        ...
    ]

    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FakeApprovedItem:
    """Minimal approved SWOT item."""

    item_id: str

    quadrant: str

    title: str

    reasoning: str

    should_feed_strategy_agent: bool


@dataclass(frozen=True, slots=True)
class FakeApprovedUpdate:
    """Minimal approved SWOT update."""

    approved_report_id: UUID

    business_id: UUID

    base_report_id: UUID

    source_proposal_id: UUID

    base_engine_version: str

    output_engine_version: str

    source_coverage: tuple[str, ...]

    items: tuple[
        FakeApprovedItem,
        ...
    ]

    approved_candidate_ids: tuple[
        str,
        ...
    ]

    rejected_candidate_ids: tuple[
        str,
        ...
    ]

    unresolved_candidate_ids: tuple[
        str,
        ...
    ]

    supporting_signal_candidate_ids: tuple[
        str,
        ...
    ]

    data_gap_candidate_ids: tuple[
        str,
        ...
    ]

    warnings: tuple[str, ...]

    ready_for_strategy: bool

    approval_complete: bool

    version: str = "1.0"


def _proposal() -> FakeProposal:
    """Build one draft proposal."""

    return FakeProposal(
        proposal_id=_PROPOSAL_ID,
        business_id=_BUSINESS_ID,
        base_report_id=_BASE_REPORT_ID,
        base_engine_version="7.0",
        proposal_version="1.0",
        status="draft",
        current_sources=(
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
        warnings=(
            "proposal warning",
        ),
        requires_human_approval=True,
    )


def _grounded_result() -> FakeGroundedResult:
    """Build one grounded result."""

    return FakeGroundedResult(
        proposal=_proposal(),
        candidates=(
            FakeCandidate(
                candidate_id="grounded:1",
                business_id=_BUSINESS_ID,
                quadrant="weakness",
            ),
        ),
        warnings=(
            "grounded warning",
        ),
    )


def _generation() -> FakeGeneration:
    """Build one successful generation metadata value."""

    return FakeGeneration(
        provider_used="vertex_ai",
        model_used="gemini-2.5-flash",
        fallback_used=False,
        raw_item_count=1,
        accepted_item_count=1,
        blocked_item_count=0,
        safe_for_update_proposal=True,
    )


def _approved_update(
    *,
    business_id: UUID = _BUSINESS_ID,
    approval_complete: bool = True,
    ready_for_strategy: bool = True,
    unresolved: tuple[str, ...] = (),
) -> FakeApprovedUpdate:
    """Build one approved SWOT update."""

    return FakeApprovedUpdate(
        approved_report_id=(
            _APPROVED_REPORT_ID
        ),
        business_id=business_id,
        base_report_id=(
            _BASE_REPORT_ID
        ),
        source_proposal_id=(
            _PROPOSAL_ID
        ),
        base_engine_version="7.0",
        output_engine_version="8.0",
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
        items=(
            FakeApprovedItem(
                item_id="W_001",
                quadrant="weakness",
                title="Recurring service delays",
                reasoning=(
                    "Approved customer evidence "
                    "identifies service delays."
                ),
                should_feed_strategy_agent=True,
            ),
            FakeApprovedItem(
                item_id="S_001",
                quadrant="strength",
                title="Strong product quality",
                reasoning=(
                    "Approved evidence supports "
                    "product quality."
                ),
                should_feed_strategy_agent=True,
            ),
        ),
        approved_candidate_ids=(
            "grounded:1",
        ),
        rejected_candidate_ids=(),
        unresolved_candidate_ids=(
            unresolved
        ),
        supporting_signal_candidate_ids=(),
        data_gap_candidate_ids=(),
        warnings=(),
        ready_for_strategy=(
            ready_for_strategy
        ),
        approval_complete=(
            approval_complete
        ),
    )


def _approved_swot_document(
    *,
    business_id: UUID = _BUSINESS_ID,
    status: str = "approved",
    approval_complete: bool = True,
    ready_for_strategy: bool = True,
) -> FakeDocument:
    """Build a persisted approved SWOT-like document."""

    return FakeDocument(
        report_id=_APPROVED_REPORT_ID,
        business_id=business_id,
        source_proposal_id=(
            _PROPOSAL_ID
        ),
        business_type="cafe",
        status=status,
        approval_complete=(
            approval_complete
        ),
        ready_for_strategy=(
            ready_for_strategy
        ),
    )


def test_serialize_normalizes_nested_domain_values():
    """Domain containers should become Mongo-safe values."""

    naive_datetime = datetime(
        2026,
        7,
        19,
        10,
        0,
    )

    serialized = persistence._serialize(
        {
            "business_id": _BUSINESS_ID,
            "created_at": naive_datetime,
            "candidate": FakeCandidate(
                candidate_id="grounded:1",
                business_id=_BUSINESS_ID,
                quadrant="weakness",
            ),
            "values": (
                "a",
                "b",
            ),
        }
    )

    assert serialized[
        "business_id"
    ] == str(
        _BUSINESS_ID
    )

    assert serialized[
        "created_at"
    ].tzinfo == UTC

    assert serialized[
        "candidate"
    ]["candidate_id"] == (
        "grounded:1"
    )

    assert serialized["values"] == [
        "a",
        "b",
    ]


@pytest.mark.asyncio
async def test_saves_draft_proposal_with_lineage(
    monkeypatch,
):
    """Draft persistence should preserve source and generation data."""

    monkeypatch.setattr(
        persistence,
        "SwotUpdateProposalDocument",
        FakeDocument,
    )

    document = await (
        persistence
        .save_swot_update_proposal(
            baseline=FakeBaseline(
                business_id=_BUSINESS_ID,
                report_id=_BASE_REPORT_ID,
                engine_version="7.0",
            ),
            generation=_generation(),
            grounded_result=(
                _grounded_result()
            ),
        )
    )

    assert document.insert_called

    assert document.status == "draft"

    assert document.proposal_id == (
        _PROPOSAL_ID
    )

    assert document.business_id == (
        _BUSINESS_ID
    )

    assert document.base_report_id == (
        _BASE_REPORT_ID
    )

    assert (
        document
        .generation_metadata[
            "provider_used"
        ]
        == "vertex_ai"
    )

    assert not (
        document
        .generation_metadata[
            "fallback_used"
        ]
    )

    assert document.source_coverage == [
        "business_profile",
        "google_maps_reviews",
        "facebook",
        "instagram",
    ]

    assert (
        document
        .candidate_snapshot[0][
            "candidate_id"
        ]
        == "grounded:1"
    )


@pytest.mark.asyncio
async def test_marks_only_draft_proposal_approved():
    """Approval should persist decisions and approved report lineage."""

    document = FakeDocument(
        status="draft",
        approval_decisions=[],
        approved_report_id=None,
        updated_at=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
    )

    decisions = (
        {
            "candidate_id": (
                "grounded:1"
            ),
            "decision": "approve",
        },
    )

    result = await (
        persistence
        .mark_proposal_approved(
            document=document,
            decisions=decisions,
            approved_report_id=(
                _APPROVED_REPORT_ID
            ),
        )
    )

    assert result.save_called

    assert result.status == "approved"

    assert result.approved_report_id == (
        _APPROVED_REPORT_ID
    )

    assert result.approval_decisions == [
        {
            "candidate_id": (
                "grounded:1"
            ),
            "decision": "approve",
        }
    ]

    assert result.updated_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_non_draft_proposal_cannot_be_approved():
    """Repeated or invalid approval transitions must fail closed."""

    document = FakeDocument(
        status="approved",
    )

    with pytest.raises(
        ValueError,
        match="Only draft",
    ):
        await (
            persistence
            .mark_proposal_approved(
                document=document,
                decisions=(),
                approved_report_id=(
                    _APPROVED_REPORT_ID
                ),
            )
        )

    assert not document.save_called


@pytest.mark.asyncio
async def test_saves_approved_swot_grouped_by_quadrant(
    monkeypatch,
):
    """Approved items should be persisted in SWOT quadrant groups."""

    monkeypatch.setattr(
        persistence,
        "SWOTReportDocument",
        FakeDocument,
    )

    document = await (
        persistence
        .save_approved_swot_report(
            approved=(
                _approved_update()
            ),
            business_type="cafe",
        )
    )

    assert document.insert_called

    assert document.status == "approved"

    assert document.approval_complete

    assert document.ready_for_strategy

    assert document.report_id == (
        _APPROVED_REPORT_ID
    )

    assert document.source_proposal_id == (
        _PROPOSAL_ID
    )

    assert len(
        document.swot_report[
            "weaknesses"
        ]
    ) == 1

    assert len(
        document.swot_report[
            "strengths"
        ]
    ) == 1

    assert document.swot_report[
        "opportunities"
    ] == []

    assert document.swot_report[
        "threats"
    ] == []

    assert (
        document.validation_results[
            "overall_status"
        ]
        == "PASS"
    )


@pytest.mark.asyncio
async def test_incomplete_approved_swot_is_not_persisted(
    monkeypatch,
):
    """Incomplete approval must never create an approved report."""

    monkeypatch.setattr(
        persistence,
        "SWOTReportDocument",
        FakeDocument,
    )

    with pytest.raises(
        ValueError,
        match="incomplete",
    ):
        await (
            persistence
            .save_approved_swot_report(
                approved=_approved_update(
                    approval_complete=False,
                ),
                business_type="cafe",
            )
        )


@pytest.mark.asyncio
async def test_unresolved_approved_swot_is_not_persisted(
    monkeypatch,
):
    """Unresolved candidates must block approved persistence."""

    monkeypatch.setattr(
        persistence,
        "SWOTReportDocument",
        FakeDocument,
    )

    with pytest.raises(
        ValueError,
        match="unresolved",
    ):
        await (
            persistence
            .save_approved_swot_report(
                approved=_approved_update(
                    unresolved=(
                        "grounded:pending",
                    ),
                ),
                business_type="cafe",
            )
        )


@pytest.mark.asyncio
async def test_saves_complete_strategy_output(
    monkeypatch,
):
    """All brand foundation and core Strategy fields should persist."""

    monkeypatch.setattr(
        persistence,
        "StrategyReportDocument",
        FakeDocument,
    )

    approved_swot = (
        _approved_swot_document()
    )

    strategy_output = {
        "engine_version": "2.0",
        "business_type": "cafe",
        "strategic_posture": (
            "balanced"
        ),
        "posture_rationale": (
            "Balanced approved SWOT."
        ),
        "positioning": {
            "statement": (
                "A service-focused cafe."
            ),
            "source_swot_item_ids": [
                "W_001",
            ],
        },
        "audience": [
            {
                "segment_name": (
                    "Service-sensitive customers"
                ),
                "source_swot_item_ids": [
                    "W_001",
                ],
            }
        ],
        "value_proposition": {
            "statement": (
                "A more responsive experience."
            ),
            "source_swot_item_ids": [
                "W_001",
            ],
        },
        "tone_of_voice": {
            "traits": [
                "clear",
                "credible",
            ],
            "source_swot_item_ids": [
                "W_001",
            ],
        },
        "content_pillars": [
            {
                "name": (
                    "Service improvement"
                ),
                "source_swot_item_ids": [
                    "W_001",
                ],
            }
        ],
        "channels": [
            {
                "channel": "instagram",
                "source_swot_item_ids": [
                    "W_001",
                ],
            }
        ],
        "goals": [
            {
                "goal": (
                    "Improve service responsiveness"
                ),
                "source_swot_item_ids": [
                    "W_001",
                ],
            }
        ],
        "tows_matrix": {
            "SO": [],
            "ST": [],
            "WO": [],
            "WT": [],
        },
        "priority_action_plan": [],
        "resource_assessment": [],
        "campaign_brief_feed": [],
        "strategy_quality_report": {
            "overall_status": "PASS",
        },
        "meta": {
            "llm_provider_used": (
                "vertex_ai"
            ),
        },
    }

    document = await (
        persistence
        .save_strategy_report(
            business_id=_BUSINESS_ID,
            approved_swot=(
                approved_swot
            ),
            strategy_output=(
                strategy_output
            ),
        )
    )

    assert document.insert_called

    assert document.business_id == (
        _BUSINESS_ID
    )

    assert document.source_swot_id == (
        _APPROVED_REPORT_ID
    )

    assert document.source_proposal_id == (
        _PROPOSAL_ID
    )

    assert document.positioning[
        "statement"
    ]

    assert len(document.audience) == 1

    assert len(
        document.content_pillars
    ) == 1

    assert len(document.channels) == 1

    assert len(document.goals) == 1

    assert (
        document
        .strategy_quality_report[
            "overall_status"
        ]
        == "PASS"
    )


@pytest.mark.asyncio
async def test_cross_business_strategy_persistence_is_rejected(
    monkeypatch,
):
    """Strategy output must not cross business boundaries."""

    monkeypatch.setattr(
        persistence,
        "StrategyReportDocument",
        FakeDocument,
    )

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        await persistence.save_strategy_report(
            business_id=_BUSINESS_ID,
            approved_swot=(
                _approved_swot_document(
                    business_id=(
                        _OTHER_BUSINESS_ID
                    )
                )
            ),
            strategy_output={},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "status",
        "approval_complete",
        "ready_for_strategy",
    ),
    [
        (
            "generated",
            True,
            True,
        ),
        (
            "approved",
            False,
            True,
        ),
        (
            "approved",
            True,
            False,
        ),
    ],
)
async def test_non_ready_swot_cannot_create_strategy(
    monkeypatch,
    status,
    approval_complete,
    ready_for_strategy,
):
    """Every persisted Strategy must come from a fully approved SWOT."""

    monkeypatch.setattr(
        persistence,
        "StrategyReportDocument",
        FakeDocument,
    )

    with pytest.raises(
        ValueError,
        match="approved and Strategy-ready",
    ):
        await persistence.save_strategy_report(
            business_id=_BUSINESS_ID,
            approved_swot=(
                _approved_swot_document(
                    status=status,
                    approval_complete=(
                        approval_complete
                    ),
                    ready_for_strategy=(
                        ready_for_strategy
                    ),
                )
            ),
            strategy_output={},
        )
