"""
Market Moment Resolver Tests
"""

import json
from datetime import date
from uuid import uuid4

from app.creative_context.country_registry import (
    load_default_country_registry,
)
from app.creative_context.date_resolvers import (
    MomentDateOverrideRegistry,
    load_default_moment_overrides,
)
from app.creative_context.moment_registry import (
    load_default_moment_registry,
)
from app.creative_context.moment_resolver import (
    calculate_selection_score,
    resolve_market_moment,
    resolve_market_moments,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    MomentResolutionRequest,
)


def _business(
    *,
    business_type: str,
    country_code: str = "SA",
) -> BusinessCreativeContext:
    """Build a minimal business context."""

    return BusinessCreativeContext(
        business_id=uuid4(),
        business_type=business_type,
        industry="test",
        country_code=country_code,
    )


def _request(
    *,
    campaign_date: date,
    country_code: str = "SA",
    objective: str = "awareness",
) -> MomentResolutionRequest:
    """Build a valid automatic resolution request."""

    return MomentResolutionRequest(
        campaign_date=campaign_date,
        target_country_code=(
            country_code
        ),
        platform="instagram",
        content_format="feed_post",
        objective=objective,
    )


def test_active_high_fit_summer_is_eligible():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    resolved, rejected, warning = (
        resolve_market_moment(
            moment=moment_registry.get(
                "summer"
            ),
            request=_request(
                campaign_date=date(
                    2026,
                    7,
                    18,
                ),
            ),
            business=_business(
                business_type=(
                    "food_and_beverage"
                ),
            ),
            country_registry=(
                country_registry
            ),
            overrides=(
                load_default_moment_overrides()
            ),
        )
    )

    assert resolved is not None
    assert resolved.status == "active"
    assert resolved.business_fit == "high"
    assert resolved.eligible is True

    assert (
        resolved.selection_score
        > 0.8
    )

    assert rejected is None
    assert warning is None


def test_low_fit_summer_is_not_automatically_eligible():
    collection = resolve_market_moments(
        request=_request(
            campaign_date=date(
                2026,
                7,
                18,
            ),
        ),
        business=_business(
            business_type="saas",
        ),
    )

    summer = next(
        item
        for item in (
            collection.resolved_moments
        )
        if item.key == "summer"
    )

    assert summer.status == "active"
    assert summer.business_fit == "low"
    assert summer.eligible is False

    rejected_keys = {
        item.key
        for item in (
            collection.rejected_moments
        )
    }

    assert "summer" in rejected_keys


def test_unsupported_objective_rejects_white_friday(
    tmp_path,
):
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    path = (
        tmp_path
        / "overrides.json"
    )

    path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "overrides": [
                    {
                        "country_code": "SA",
                        "moment_key": (
                            "white_friday"
                        ),
                        "year": 2026,
                        "active_from": (
                            "2026-11-20"
                        ),
                        "active_until": (
                            "2026-11-30"
                        ),
                        "source": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    overrides = (
        MomentDateOverrideRegistry
        .from_json_file(
            path
        )
    )

    resolved, rejected, warning = (
        resolve_market_moment(
            moment=moment_registry.get(
                "white_friday"
            ),
            request=_request(
                campaign_date=date(
                    2026,
                    11,
                    25,
                ),
                objective="awareness",
            ),
            business=_business(
                business_type="retail",
            ),
            country_registry=(
                country_registry
            ),
            overrides=overrides,
        )
    )

    assert resolved is not None
    assert resolved.status == "active"
    assert resolved.eligible is False

    assert rejected is not None

    assert (
        "objective"
        in rejected.reason.lower()
    )

    assert warning is None


def test_inactive_moment_receives_zero_score():
    score = calculate_selection_score(
        status="inactive",
        business_fit="high",
        objective_supported=True,
        priority=100,
    )

    assert score == 0.0


def test_target_country_controls_country_scope():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    resolved, rejected, warning = (
        resolve_market_moment(
            moment=moment_registry.get(
                "saudi_national_day"
            ),
            request=_request(
                campaign_date=date(
                    2026,
                    9,
                    23,
                ),
                country_code="AE",
            ),
            business=_business(
                business_type="retail",
                country_code="SA",
            ),
            country_registry=(
                country_registry
            ),
            overrides=(
                load_default_moment_overrides()
            ),
        )
    )

    assert resolved is None
    assert rejected is not None

    assert (
        "target country"
        in rejected.reason.lower()
    )

    assert warning is None


def test_country_override_resolves_national_moment(
    tmp_path,
):
    path = (
        tmp_path
        / "overrides.json"
    )

    path.write_text(
        json.dumps(
            {
                "registry_version": "1",
                "overrides": [
                    {
                        "country_code": "SA",
                        "moment_key": (
                            "saudi_national_day"
                        ),
                        "year": 2026,
                        "active_from": (
                            "2026-09-20"
                        ),
                        "active_until": (
                            "2026-09-23"
                        ),
                        "source": (
                            "test_calendar"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    overrides = (
        MomentDateOverrideRegistry
        .from_json_file(
            path
        )
    )

    collection = resolve_market_moments(
        request=_request(
            campaign_date=date(
                2026,
                9,
                22,
            ),
        ),
        business=_business(
            business_type="retail",
        ),
        overrides=overrides,
    )

    national_day = next(
        item
        for item in (
            collection.resolved_moments
        )
        if (
            item.key
            == "saudi_national_day"
        )
    )

    assert national_day.status == "active"
    assert national_day.eligible is True

    assert any(
        reference.startswith(
            "moment-override:"
        )
        for reference in (
            national_day
            .evidence_references
        )
    )


def test_full_resolution_is_sorted_by_score():
    collection = resolve_market_moments(
        request=_request(
            campaign_date=date(
                2026,
                7,
                18,
            ),
        ),
        business=_business(
            business_type=(
                "food_and_beverage"
            ),
        ),
    )

    scores = [
        item.selection_score
        for item in (
            collection.resolved_moments
        )
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )

    summer = next(
        item
        for item in (
            collection.resolved_moments
        )
        if item.key == "summer"
    )

    assert summer.eligible is True

    assert any(
        "country/year override"
        in warning
        for warning in collection.warnings
    )