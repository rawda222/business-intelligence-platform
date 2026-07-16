"""
Trend Evidence API Tests

Verifies the evidence endpoint by patching the ownership guard and
the report builder so the endpoint runs without MongoDB access.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import trends as trends_module
from app.core.dependencies import get_current_user
from app.main import app
from app.services.business_trend_report_service import (
    BusinessTrendReport,
)
from app.services.post_trend_service import (
    PostsPerWeekBucket,
    PostsPerWeekTrend,
)
from app.services.review_trend_service import (
    ReviewsPerMonthBucket,
    ReviewsPerMonthTrend,
)
from app.services.trend_foundation_service import (
    BusinessTrendFoundationStats,
)


@pytest.mark.asyncio
async def test_evidence_endpoint_returns_evidence_entries(
    monkeypatch,
):
    """
    The evidence endpoint returns evidence entries produced from
    a synthetic BusinessTrendReport.
    """

    business_id = uuid4()

    async def fake_current_user():
        return SimpleNamespace(
            id=uuid4(),
        )

    async def fake_require_ownership(
        **kwargs,
    ):
        return None

    async def fake_build_report(
        **kwargs,
    ):
        range_start = datetime(
            2026,
            6,
            1,
            0,
            0,
            tzinfo=UTC,
        )

        range_end = datetime(
            2026,
            9,
            1,
            0,
            0,
            tzinfo=UTC,
        )

        foundation = (
            BusinessTrendFoundationStats(
                business_id=business_id,
                total_posts=0,
                total_post_metric_snapshots=(
                    0
                ),
                total_comments=0,
                total_customer_reviews=0,
                posts_by_platform={},
                comments_by_platform={},
                reviews_by_source={},
            )
        )

        posts_per_week = PostsPerWeekTrend(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
            buckets=[
                PostsPerWeekBucket(
                    week_start=date(
                        2026,
                        7,
                        6,
                    ),
                    post_count=0,
                ),
            ],
            total_posts=0,
        )

        reviews_per_month = (
            ReviewsPerMonthTrend(
                business_id=business_id,
                source="google_maps",
                range_start=range_start,
                range_end=range_end,
                buckets=[
                    ReviewsPerMonthBucket(
                        month_start=date(
                            2026,
                            6,
                            1,
                        ),
                        review_count=0,
                        meaningful_review_count=(
                            0
                        ),
                        rating_average=None,
                    ),
                ],
                total_reviews=0,
                total_meaningful_reviews=0,
            )
        )

        return BusinessTrendReport(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
            review_source="google_maps",
            foundation=foundation,
            posts_per_week=posts_per_week,
            reviews_per_month=(
                reviews_per_month
            ),
            engagement_curves=[],
        )

    monkeypatch.setattr(
        trends_module,
        "_require_business_ownership",
        fake_require_ownership,
    )

    monkeypatch.setattr(
        trends_module,
        "build_business_trend_report",
        fake_build_report,
    )

    app.dependency_overrides[
        get_current_user
    ] = fake_current_user

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            (
                "/api/v1/businesses/"
                f"{business_id}"
                "/trends/evidence"
            ),
            params={
                "range_start": (
                    "2026-06-01T00:00:00"
                    "+00:00"
                ),
                "range_end": (
                    "2026-09-01T00:00:00"
                    "+00:00"
                ),
            },
        )

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["review_source"]
        == "google_maps"
    )

    entries = body["evidence"]

    assert isinstance(entries, list)

    categories = {
        entry["category"]
        for entry in entries
    }

    assert "publishing" in categories
    assert "reviews" in categories

    for entry in entries:
        assert isinstance(
            entry["confidence"],
            (int, float),
        )

        assert entry["reference"]
        assert entry["description"]