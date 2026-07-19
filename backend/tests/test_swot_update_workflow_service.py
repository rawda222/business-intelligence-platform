"""
SWOT Update Workflow Service Tests

Tests production orchestration without MongoDB or Vertex AI.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.swot_update_workflow_service import (
    create_swot_update_proposal_workflow,
)


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

_RANGE_START = datetime(
    2026,
    6,
    1,
    tzinfo=UTC,
)

_RANGE_END = datetime(
    2026,
    7,
    1,
    tzinfo=UTC,
)


def _baseline_document(
    *,
    business_id: UUID = _BUSINESS_ID,
):
    """Build one stored SWOT-like baseline."""

    return SimpleNamespace(
        report_id=_BASE_REPORT_ID,
        business_id=business_id,
        engine_version="7.0",
        source_coverage=[
            "business_profile",
            "google_maps_reviews",
        ],
        swot_report={
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        },
    )


@pytest.mark.asyncio
async def test_orchestrates_complete_proposal_workflow():
    """All workflow stages should execute in order."""

    calls: list[str] = []

    baseline = SimpleNamespace(
        business_id=_BUSINESS_ID,
        report_id=_BASE_REPORT_ID,
    )

    customer_voice = SimpleNamespace(
        business_id=_BUSINESS_ID,
    )

    trend_report = SimpleNamespace(
        business_id=_BUSINESS_ID,
    )

    intelligence = SimpleNamespace(
        business_id=_BUSINESS_ID,
    )

    bundle = SimpleNamespace(
        business_id=_BUSINESS_ID,
    )

    generation = SimpleNamespace(
        business_id=_BUSINESS_ID,
    )

    proposal = SimpleNamespace(
        current_sources=(
            "business_profile",
            "google_maps_reviews",
            "facebook",
            "instagram",
        ),
    )

    grounded = SimpleNamespace(
        business_id=_BUSINESS_ID,
        proposal=proposal,
        warnings=(
            "workflow warning",
        ),
        safe_for_approval_workflow=True,
    )

    persisted = SimpleNamespace(
        business_id=_BUSINESS_ID,
        proposal_id=_PROPOSAL_ID,
    )

    async def load_baseline_fn(
        *,
        business_id,
    ):
        calls.append(
            "load_baseline"
        )

        assert business_id == (
            _BUSINESS_ID
        )

        return _baseline_document()

    def normalize_baseline_fn(
        **kwargs,
    ):
        calls.append(
            "normalize_baseline"
        )

        assert kwargs[
            "report_id"
        ] == _BASE_REPORT_ID

        return baseline

    async def load_customer_voice_fn(
        **kwargs,
    ):
        calls.append(
            "load_customer_voice"
        )

        assert kwargs[
            "business_name"
        ] == "Example Cafe"

        return customer_voice

    async def build_trend_report_fn(
        **kwargs,
    ):
        calls.append(
            "build_trend_report"
        )

        assert kwargs[
            "review_source"
        ] == "google_maps"

        return trend_report

    def build_trend_intelligence_fn(
        value,
    ):
        calls.append(
            "build_trend_intelligence"
        )

        assert value is trend_report

        return intelligence

    def build_bundle_fn(
        **kwargs,
    ):
        calls.append(
            "build_bundle"
        )

        assert (
            kwargs["customer_voice"]
            is customer_voice
        )

        assert (
            kwargs[
                "trend_intelligence"
            ]
            is intelligence
        )

        return bundle

    def generate_fn(
        **kwargs,
    ):
        calls.append(
            "generate"
        )

        assert kwargs[
            "bundle"
        ] is bundle

        return generation

    def build_proposal_fn(
        **kwargs,
    ):
        calls.append(
            "build_proposal"
        )

        assert kwargs[
            "baseline"
        ] is baseline

        assert kwargs[
            "bundle"
        ] is bundle

        assert kwargs[
            "generation"
        ] is generation

        return grounded

    async def save_proposal_fn(
        **kwargs,
    ):
        calls.append(
            "save_proposal"
        )

        assert kwargs[
            "grounded_result"
        ] is grounded

        return persisted

    result = await (
        create_swot_update_proposal_workflow(
            business_id=_BUSINESS_ID,
            business_name="Example Cafe",
            business_type="cafe",
            range_start=_RANGE_START,
            range_end=_RANGE_END,
            load_baseline_fn=(
                load_baseline_fn
            ),
            normalize_baseline_fn=(
                normalize_baseline_fn
            ),
            load_customer_voice_fn=(
                load_customer_voice_fn
            ),
            build_trend_report_fn=(
                build_trend_report_fn
            ),
            build_trend_intelligence_fn=(
                build_trend_intelligence_fn
            ),
            build_bundle_fn=(
                build_bundle_fn
            ),
            generate_fn=generate_fn,
            build_proposal_fn=(
                build_proposal_fn
            ),
            save_proposal_fn=(
                save_proposal_fn
            ),
        )
    )

    assert calls == [
        "load_baseline",
        "normalize_baseline",
        "load_customer_voice",
        "build_trend_report",
        "build_trend_intelligence",
        "build_bundle",
        "generate",
        "build_proposal",
        "save_proposal",
    ]

    assert result.business_id == (
        _BUSINESS_ID
    )

    assert result.proposal_id == (
        _PROPOSAL_ID
    )

    assert result.baseline_report_id == (
        _BASE_REPORT_ID
    )

    assert result.persisted_proposal is (
        persisted
    )

    assert result.source_coverage == (
        "business_profile",
        "google_maps_reviews",
        "facebook",
        "instagram",
    )

    assert result.warnings == (
        "workflow warning",
    )


@pytest.mark.asyncio
async def test_missing_baseline_blocks_workflow():
    """A proposal cannot be created without a stored baseline."""

    async def load_baseline_fn(
        *,
        business_id,
    ):
        assert business_id == (
            _BUSINESS_ID
        )

        return None

    with pytest.raises(
        ValueError,
        match="baseline is required",
    ):
        await (
            create_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                business_name=(
                    "Example Cafe"
                ),
                business_type="cafe",
                range_start=_RANGE_START,
                range_end=_RANGE_END,
                load_baseline_fn=(
                    load_baseline_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_cross_business_baseline_is_rejected():
    """Stored baseline tenant identity must match the request."""

    async def load_baseline_fn(
        *,
        business_id,
    ):
        return _baseline_document(
            business_id=(
                _OTHER_BUSINESS_ID
            )
        )

    with pytest.raises(
        ValueError,
        match="business_id",
    ):
        await (
            create_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                business_name=(
                    "Example Cafe"
                ),
                business_type="cafe",
                range_start=_RANGE_START,
                range_end=_RANGE_END,
                load_baseline_fn=(
                    load_baseline_fn
                ),
            )
        )


@pytest.mark.asyncio
async def test_invalid_range_is_rejected_before_loading():
    """Invalid date ranges must fail before external reads."""

    load_called = False

    async def load_baseline_fn(
        *,
        business_id,
    ):
        nonlocal load_called

        load_called = True

        return _baseline_document()

    with pytest.raises(
        ValueError,
        match="range_start",
    ):
        await (
            create_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                business_name=(
                    "Example Cafe"
                ),
                business_type="cafe",
                range_start=_RANGE_END,
                range_end=_RANGE_START,
                load_baseline_fn=(
                    load_baseline_fn
                ),
            )
        )

    assert not load_called


@pytest.mark.asyncio
async def test_negative_engagement_limit_is_rejected():
    """A negative report bound must fail closed."""

    with pytest.raises(
        ValueError,
        match="max_engagement_curves",
    ):
        await (
            create_swot_update_proposal_workflow(
                business_id=(
                    _BUSINESS_ID
                ),
                business_name=(
                    "Example Cafe"
                ),
                business_type="cafe",
                range_start=_RANGE_START,
                range_end=_RANGE_END,
                max_engagement_curves=-1,
            )
        )