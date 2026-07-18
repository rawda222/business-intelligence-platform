"""
Creative Theme Selector Tests
"""

from datetime import date
from uuid import uuid4

import pytest

from app.creative_context.exceptions import (
    ThemeSelectionError,
)
from app.creative_context.moment_resolver import (
    MarketMomentResolutionCollection,
    resolve_market_moments,
)
from app.creative_context.schemas import (
    BusinessCreativeContext,
    MomentResolutionRequest,
    ResolvedMarketMoment,
)
from app.creative_context.theme_selector import (
    select_theme_moments,
)


def _business(
    *,
    business_type: str = "food_and_beverage",
):
    """Build a minimal business context."""

    return BusinessCreativeContext(
        business_id=uuid4(),
        business_type=business_type,
        industry="cafe",
        country_code="SA",
    )


def _request(
    *,
    campaign_date: date,
    selection_mode: str = "automatic",
    moment_override: str | None = None,
):
    """Build one selector request."""

    return MomentResolutionRequest(
        campaign_date=campaign_date,
        target_country_code="SA",
        platform="instagram",
        content_format="feed_post",
        objective="awareness",
        selection_mode=selection_mode,
        moment_override=moment_override,
    )


def _resolved_moment(
    *,
    key: str,
    status: str,
    business_fit: str,
    eligible: bool,
    selection_score: float,
    priority: int,
):
    """Build a synthetic resolved moment."""

    return ResolvedMarketMoment(
        key=key,
        display_name=(
            key.replace(
                "_",
                " ",
            ).title()
        ),
        moment_type="commercial",
        campaign_date=date(
            2026,
            7,
            18,
        ),
        active_from=date(
            2026,
            7,
            1,
        ),
        active_until=date(
            2026,
            7,
            31,
        ),
        status=status,
        business_fit=business_fit,
        eligible=eligible,
        priority=priority,
        selection_score=selection_score,
    )


def test_automatic_selects_active_highest_score():
    """
    Active moments should rank before upcoming moments,
    even when the upcoming score is slightly higher.
    """

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(
                _resolved_moment(
                    key="summer",
                    status="active",
                    business_fit="high",
                    eligible=True,
                    selection_score=0.90,
                    priority=70,
                ),
                _resolved_moment(
                    key="back_to_school",
                    status="upcoming",
                    business_fit="high",
                    eligible=True,
                    selection_score=0.95,
                    priority=80,
                ),
            ),
            rejected_moments=(),
            warnings=(),
        )
    )

    decision = select_theme_moments(
        request=_request(
            campaign_date=date(
                2026,
                7,
                18,
            ),
        ),
        collection=collection,
    )

    assert (
        decision.primary_moment
        is not None
    )

    assert (
        decision.primary_moment.key
        == "summer"
    )

    assert (
        decision.secondary_moments[0].key
        == "back_to_school"
    )


def test_automatic_falls_back_when_no_candidate():
    """Automatic selection should fall back when nothing is eligible."""

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(
                _resolved_moment(
                    key="summer",
                    status="active",
                    business_fit="low",
                    eligible=False,
                    selection_score=0.60,
                    priority=70,
                ),
            ),
            rejected_moments=(),
            warnings=(),
        )
    )

    decision = select_theme_moments(
        request=_request(
            campaign_date=date(
                2026,
                7,
                18,
            ),
        ),
        collection=collection,
    )

    assert decision.primary_moment is None

    assert (
        decision.fallback_reason
        is not None
    )


def test_brand_only_never_selects_moment():
    """Brand-only mode should not select seasonal moments."""

    resolution_request = _request(
        campaign_date=date(
            2026,
            7,
            18,
        ),
    )

    collection = resolve_market_moments(
        request=resolution_request,
        business=_business(),
    )

    brand_only_request = _request(
        campaign_date=date(
            2026,
            7,
            18,
        ),
        selection_mode="brand_only",
    )

    decision = select_theme_moments(
        request=brand_only_request,
        collection=collection,
    )

    assert decision.primary_moment is None

    assert (
        decision.secondary_moments
        == ()
    )

    assert (
        decision.fallback_reason
        is not None
    )

    assert (
        "brand-only"
        in decision.fallback_reason.lower()
    )


def test_user_override_allows_low_fit():
    """A user override may select a low-fit active moment."""

    resolution_request = _request(
        campaign_date=date(
            2026,
            7,
            18,
        ),
    )

    collection = resolve_market_moments(
        request=resolution_request,
        business=_business(
            business_type="saas",
        ),
    )

    override_request = _request(
        campaign_date=date(
            2026,
            7,
            18,
        ),
        selection_mode="user_override",
        moment_override="summer",
    )

    decision = select_theme_moments(
        request=override_request,
        collection=collection,
    )

    assert (
        decision.primary_moment
        is not None
    )

    assert (
        decision.primary_moment.key
        == "summer"
    )

    assert (
        decision.primary_moment.business_fit
        == "low"
    )


def test_user_override_rejects_inactive_moment():
    """A user override must not force an inactive moment."""

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(
                _resolved_moment(
                    key="valentines",
                    status="inactive",
                    business_fit="high",
                    eligible=False,
                    selection_score=0.0,
                    priority=65,
                ),
            ),
            rejected_moments=(),
            warnings=(),
        )
    )

    with pytest.raises(
        ThemeSelectionError,
        match="not active or upcoming",
    ):
        select_theme_moments(
            request=_request(
                campaign_date=date(
                    2026,
                    7,
                    18,
                ),
                selection_mode=(
                    "user_override"
                ),
                moment_override=(
                    "valentines"
                ),
            ),
            collection=collection,
        )


def test_user_override_rejects_missing_moment():
    """An unresolved override key should fail explicitly."""

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(),
            rejected_moments=(),
            warnings=(),
        )
    )

    with pytest.raises(
        ThemeSelectionError,
        match="could not be resolved",
    ):
        select_theme_moments(
            request=_request(
                campaign_date=date(
                    2026,
                    7,
                    18,
                ),
                selection_mode=(
                    "user_override"
                ),
                moment_override=(
                    "unknown_moment"
                ),
            ),
            collection=collection,
        )


def test_tie_is_broken_by_priority_then_key():
    """Priority should break equal status and score ties."""

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(
                _resolved_moment(
                    key="moment_b",
                    status="active",
                    business_fit="high",
                    eligible=True,
                    selection_score=0.90,
                    priority=70,
                ),
                _resolved_moment(
                    key="moment_a",
                    status="active",
                    business_fit="high",
                    eligible=True,
                    selection_score=0.90,
                    priority=80,
                ),
            ),
            rejected_moments=(),
            warnings=(),
        )
    )

    decision = select_theme_moments(
        request=_request(
            campaign_date=date(
                2026,
                7,
                18,
            ),
        ),
        collection=collection,
        max_secondary_moments=0,
    )

    assert (
        decision.primary_moment
        is not None
    )

    assert (
        decision.primary_moment.key
        == "moment_a"
    )


def test_invalid_secondary_limit_is_rejected():
    """The configured secondary limit must remain bounded."""

    collection = (
        MarketMomentResolutionCollection(
            resolved_moments=(),
            rejected_moments=(),
            warnings=(),
        )
    )

    with pytest.raises(
        ThemeSelectionError,
        match="between 0 and 3",
    ):
        select_theme_moments(
            request=_request(
                campaign_date=date(
                    2026,
                    7,
                    18,
                ),
            ),
            collection=collection,
            max_secondary_moments=4,
        )