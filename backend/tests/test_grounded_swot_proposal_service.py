"""
Grounded SWOT Proposal Service Tests
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    SentimentBalance,
)
from app.services.grounded_swot_output_validator import (
    GroundedSwotValidationResult,
    SafeGroundedSwotItem,
)
from app.services.grounded_swot_proposal_service import (
    build_grounded_swot_update_proposal,
    build_grounded_swot_initial_proposal,
)
from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
)


_BUSINESS_ID = UUID(
    "10101010-aaaa-bbbb-cccc-101010101010"
)

_OTHER_BUSINESS_ID = UUID(
    "20202020-aaaa-bbbb-cccc-202020202020"
)

_REPORT_ID = UUID(
    "30303030-aaaa-bbbb-cccc-303030303030"
)


def _baseline(
    *,
    business_id: UUID = _BUSINESS_ID,
) -> NormalizedSwotBaseline:
    """Build an empty normalized baseline."""

    return NormalizedSwotBaseline(
        business_id=business_id,
        report_id=_REPORT_ID,
        engine_version="7.0",
        items=(),
        source_coverage=(
            "business_profile",
            "google_maps_reviews",
        ),
        warnings=(),
    )


def _theme() -> ReviewTheme:
    """Build one cross-source customer theme."""

    return ReviewTheme(
        theme_category="service",
        entity_type="target_business",
        frequency=3,
        sentiment_balance=(
            SentimentBalance(
                positive=0,
                negative=3,
                neutral=0,
                mixed=0,
            )
        ),
        confidence_score=0.8,
        source_platforms=[
            "google_maps",
            "facebook",
            "instagram",
        ],
        evidence_refs=[
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ],
    )


def _bundle(
    *,
    business_id: UUID = _BUSINESS_ID,
):
    """Build the minimum Strong SWOT bundle."""

    profile = BusinessProfile(
        business_name="Example Cafe",
        business_type="cafe",
        themes=[
            _theme()
        ],
    )

    return SimpleNamespace(
        business_id=business_id,
        swot_profile=profile,
        trend_candidates=(),
    )


def _safe_item() -> SafeGroundedSwotItem:
    """Build one accepted grounded Weakness."""

    return SafeGroundedSwotItem(
        quadrant="weaknesses",
        title=(
            "Consistent customer dissatisfaction "
            "with service speed"
        ),
        reasoning=(
            "Customer evidence repeatedly identifies "
            "slow service and long waiting times."
        ),
        source_theme="service",
        tags=(
            "service_speed",
            "operations",
        ),
        importance=8.0,
        impact=7.5,
        confidence=0.8,
        frequency=3,
        evidence_references=(
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        ),
        origin="customer_theme",
        claim_strength=(
            "internally_supported"
        ),
        requires_manual_review=True,
        should_feed_strategy_agent=False,
    )


def _generation(
    *,
    business_id: UUID = _BUSINESS_ID,
    safe: bool = True,
):
    """Build one grounded generation result-like value."""

    item = _safe_item()

    validation = (
        GroundedSwotValidationResult(
            business_id=business_id,
            valid=True,
            accepted_items=(
                item,
            ),
            blocked_items=(),
            violations=(),
            allowed_evidence_references=(
                item.evidence_references
            ),
            observed_evidence_references=(
                item.evidence_references
            ),
            requires_human_review=True,
        )
    )

    return SimpleNamespace(
        business_id=business_id,
        validation=validation,
        accepted_items=(
            item,
        ),
        safe_for_update_proposal=safe,
        warnings=(),
    )


def test_builds_add_proposal_from_grounded_item():
    """A grounded item should become a draft addition."""

    result = (
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert result.candidate_count == 1

    assert result.safe_for_approval_workflow

    assert result.requires_human_approval

    assert len(
        result.proposal.add_items
    ) == 1

    candidate = result.candidates[0]

    assert candidate.quadrant == (
        "weakness"
    )

    assert candidate.disposition == (
        "swot_candidate"
    )

    assert candidate.decision == (
        "manual_review"
    )

    assert (
        candidate
        .should_feed_strategy_agent
    )

    assert candidate.requires_manual_review

    assert candidate.claim_strength == (
        "directional"
    )

    proposal_item = (
        result.proposal.add_items[0]
    )

    assert not (
        proposal_item
        .should_feed_strategy_agent
    )

    assert (
        proposal_item
        .eligible_for_strategy_after_approval
    )


def test_preserves_cross_source_evidence_and_sources():
    """Google, Facebook, and Instagram lineage must survive."""

    result = (
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    candidate = result.candidates[0]

    assert (
        candidate.evidence_references
        == (
            "google_maps:review:g-1",
            "facebook:comment:f-1",
            "instagram:comment:i-1",
        )
    )

    assert candidate.supporting_sources == (
        "google_maps_reviews",
        "facebook",
        "instagram",
    )


def test_supporting_metrics_are_python_controlled():
    """Frequency and scores should come from the safe item."""

    result = (
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    metrics = dict(
        result
        .candidates[0]
        .supporting_metrics
    )

    assert metrics["frequency"] == 3

    assert metrics["importance"] == 8.0

    assert metrics["impact"] == 7.5

    assert metrics["source_theme"] == (
        "service"
    )

    assert metrics["origin"] == (
        "customer_theme"
    )


def test_candidate_id_is_deterministic():
    """Identical grounded evidence should create the same ID."""

    first = (
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    second = (
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    assert (
        first.candidates[0].candidate_id
        == second.candidates[0].candidate_id
    )

    assert (
        first.proposal.proposal_id
        == second.proposal.proposal_id
    )


def test_unsafe_generation_is_rejected():
    """Unsafe generation must never reach proposal building."""

    with pytest.raises(
        ValueError,
        match="not safe",
    ):
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(
                safe=False
            ),
        )


def test_cross_business_bundle_is_rejected():
    """A bundle from another tenant must fail closed."""

    with pytest.raises(
        ValueError,
        match="bundle business_id",
    ):
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(
                business_id=(
                    _OTHER_BUSINESS_ID
                )
            ),
            generation=_generation(),
        )


def test_cross_business_generation_is_rejected():
    """A generation result from another tenant must fail closed."""

    with pytest.raises(
        ValueError,
        match="generation business_id",
    ):
        build_grounded_swot_update_proposal(
            baseline=_baseline(),
            bundle=_bundle(),
            generation=_generation(
                business_id=(
                    _OTHER_BUSINESS_ID
                )
            ),
        )

def test_builds_initial_proposal_without_baseline():
    """
    Initial SWOT proposal should be created without
    an existing baseline report.
    """

    result = (
        build_grounded_swot_initial_proposal(
            bundle=_bundle(),
            generation=_generation(),
        )
    )

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert result.proposal.proposal_mode == (
        "initial"
    )

    assert result.proposal.base_report_id is None

    assert (
        result.proposal.base_engine_version
        is None
    )

    assert result.proposal.status == (
        "draft"
    )

    assert (
        result.requires_human_approval
        is True
    )

    assert (
        result.safe_for_approval_workflow
        is True
    )

    assert (
        result.candidate_count > 0
    )

    assert len(
        result.proposal.add_items
    ) > 0        