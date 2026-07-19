"""
Approved SWOT to Strategy Service Tests
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.approved_swot_builder import (
    ApprovedSwotItem,
    ApprovedSwotUpdate,
)
from app.services.approved_swot_strategy_service import (
    build_strategy_input_from_approved_swot,
    run_strategy_from_approved_swot,
)


_BUSINESS_ID = UUID(
    "40404040-aaaa-bbbb-cccc-404040404040"
)

_OTHER_BUSINESS_ID = UUID(
    "50505050-aaaa-bbbb-cccc-505050505050"
)

_APPROVED_REPORT_ID = UUID(
    "60606060-aaaa-bbbb-cccc-606060606060"
)

_BASE_REPORT_ID = UUID(
    "70707070-aaaa-bbbb-cccc-707070707070"
)

_PROPOSAL_ID = UUID(
    "80808080-aaaa-bbbb-cccc-808080808080"
)


class FakeStrategyAgent:
    """Deterministic Strategy Agent replacement."""

    def __init__(self):
        self.received_input = None

        self.output = {
            "strategy": "generated"
        }

    def run(
        self,
        swot_output,
    ):
        self.received_input = (
            swot_output
        )

        return self.output


def _approved_item(
    *,
    item_id: str = "approved:1",
    quadrant: str = "weakness",
    eligible: bool = True,
    manual_review_only: bool = False,
) -> ApprovedSwotItem:
    """Build one approved SWOT item."""

    return ApprovedSwotItem(
        item_id=item_id,
        quadrant=quadrant,
        title="Recurring service delays",
        reasoning=(
            "Customer evidence identifies "
            "slow service and waiting times."
        ),
        source_theme="service",
        confidence=0.8,
        strategic_priority=8.0,
        claim_strength="directional",
        evidence_references=(
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ),
        supporting_sources=(
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
        supporting_metrics=(
            (
                "frequency",
                3,
            ),
        ),
        should_feed_strategy_agent=(
            eligible
        ),
        manual_review_only=(
            manual_review_only
        ),
        origin="approved_candidate",
        base_item_id=None,
        source_candidate_id=(
            "grounded:candidate-1"
        ),
    )


def _approved_update(
    *,
    business_id: UUID = _BUSINESS_ID,
    items: tuple[
        ApprovedSwotItem,
        ...
    ] | None = None,
    approval_complete: bool = True,
    ready_for_strategy: bool = True,
    unresolved: tuple[str, ...] = (),
) -> ApprovedSwotUpdate:
    """Build one approved SWOT update."""

    if items is None:
        items = (
            _approved_item(),
        )

    return ApprovedSwotUpdate(
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
        items=items,
        approved_candidate_ids=(
            "grounded:candidate-1",
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


def test_builds_strategy_payload_from_approved_swot():
    """Eligible approved items should enter the correct quadrant."""

    payload = (
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update()
            ),
            business_type="cafe",
            benchmark_quality=(
                "unavailable"
            ),
            expected_business_id=(
                _BUSINESS_ID
            ),
        )
    )

    assert payload[
        "validation_results"
    ]["overall_status"] == "PASS"

    assert payload[
        "business_type"
    ] == "cafe"

    assert len(
        payload["swot_report"][
            "weaknesses"
        ]
    ) == 1

    assert payload["swot_report"][
        "strengths"
    ] == []

    item = payload[
        "swot_report"
    ]["weaknesses"][0]

    assert item["item_id"] == (
        "approved:1"
    )

    assert item[
        "should_feed_strategy_agent"
    ]

    assert not item[
        "manual_review_only"
    ]

    assert item["scoring"] == {
        "strategic_priority": 8.0,
        "confidence": 0.8,
    }


def test_excludes_non_eligible_and_manual_review_items():
    """Only explicitly eligible approved items may reach Strategy."""

    approved = _approved_update(
        items=(
            _approved_item(
                item_id="eligible",
            ),
            _approved_item(
                item_id="not-eligible",
                eligible=False,
            ),
            _approved_item(
                item_id="manual",
                eligible=True,
                manual_review_only=True,
            ),
        )
    )

    payload = (
        build_strategy_input_from_approved_swot(
            approved=approved,
            business_type="cafe",
        )
    )

    items = payload[
        "swot_report"
    ]["weaknesses"]

    assert [
        item["item_id"]
        for item in items
    ] == [
        "eligible"
    ]


def test_strategy_filter_will_receive_pass_status():
    """The Strategy Python gate should receive validation PASS."""

    payload = (
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update()
            ),
            business_type="cafe",
        )
    )

    assert payload[
        "validation_results"
    ] == {
        "overall_status": "PASS",
        "violations": [],
    }

    assert payload[
        "strategic_context"
    ]["benchmark_quality"] == (
        "unavailable"
    )


def test_incomplete_approval_is_rejected():
    """Incomplete human decisions must block Strategy."""

    with pytest.raises(
        ValueError,
        match="incomplete",
    ):
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update(
                    approval_complete=False
                )
            ),
            business_type="cafe",
        )


def test_unresolved_candidates_are_rejected():
    """Unresolved proposal candidates must block Strategy."""

    with pytest.raises(
        ValueError,
        match="unresolved",
    ):
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update(
                    unresolved=(
                        "candidate:pending",
                    )
                )
            ),
            business_type="cafe",
        )


def test_not_ready_report_is_rejected():
    """A non-ready approved report must not reach Strategy."""

    with pytest.raises(
        ValueError,
        match="not ready",
    ):
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update(
                    ready_for_strategy=False
                )
            ),
            business_type="cafe",
        )


def test_no_strategy_eligible_items_is_rejected():
    """Strategy should not run on an empty eligible SWOT."""

    with pytest.raises(
        ValueError,
        match="no Strategy-eligible",
    ):
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update(
                    items=(
                        _approved_item(
                            eligible=False
                        ),
                    )
                )
            ),
            business_type="cafe",
        )


def test_cross_business_approved_update_is_rejected():
    """Tenant mismatch must fail closed."""

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        build_strategy_input_from_approved_swot(
            approved=(
                _approved_update(
                    business_id=(
                        _OTHER_BUSINESS_ID
                    )
                )
            ),
            business_type="cafe",
            expected_business_id=(
                _BUSINESS_ID
            ),
        )


def test_runs_strategy_agent_with_approved_payload():
    """The final service should pass only the approved payload."""

    agent = FakeStrategyAgent()

    result = (
        run_strategy_from_approved_swot(
            approved=(
                _approved_update()
            ),
            business_type="cafe",
            benchmark_quality=(
                "unavailable"
            ),
            expected_business_id=(
                _BUSINESS_ID
            ),
            strategy_agent=agent,
        )
    )

    assert result.strategy_executed

    assert result.eligible_item_count == 1

    assert result.excluded_item_count == 0

    assert (
        agent.received_input
        is result.strategy_input
    )

    assert result.strategy_output == {
        "strategy": "generated"
    }


def test_agent_without_run_is_rejected():
    """Injected Strategy dependencies must expose run()."""

    with pytest.raises(
        TypeError,
        match="run",
    ):
        run_strategy_from_approved_swot(
            approved=(
                _approved_update()
            ),
            business_type="cafe",
            strategy_agent=object(),
        )