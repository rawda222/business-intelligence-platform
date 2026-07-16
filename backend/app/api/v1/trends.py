"""
Trend Analysis Endpoints

Exposes tenant-scoped trend endpoints backed by the trend services.

Every endpoint:

- Requires an authenticated user via get_current_user.
- Validates business ownership via get_business_by_id and
  owner_id=current_user.id.
- Returns 404 when the business does not belong to the caller.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.business_service import (
    get_business_by_id,
)
from app.services.post_engagement_curve_service import (
    PostEngagementCurvePostNotFoundError,
    get_post_engagement_curve,
)
from app.services.post_trend_service import (
    get_posts_per_week_trend,
)
from app.services.review_trend_service import (
    get_reviews_per_month_trend,
)
from app.services.trend_foundation_service import (
    get_business_trend_foundation_stats,
)


router = APIRouter(
    prefix="/businesses",
    tags=["Trends"],
)


# ============================================================
# Business Ownership Guard
# ============================================================
async def _require_business_ownership(
    *,
    db: AsyncSession,
    business_id: UUID,
    owner_id: UUID,
) -> None:
    """
    Ensure the current user owns the requested business.

    Raises:
        HTTPException 404:
            The business does not exist or does not belong to the
            current user.
    """

    business = await get_business_by_id(
        db=db,
        business_id=business_id,
        owner_id=owner_id,
    )

    if business is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Business not found",
        )


# ============================================================
# GET /businesses/{business_id}/trends/foundation
# ============================================================
@router.get(
    "/{business_id}/trends/foundation",
    summary=(
        "Get foundational trend statistics"
    ),
)
async def read_business_trend_foundation(
    business_id: UUID,
    current_user: User = Depends(
        get_current_user,
    ),
    db: AsyncSession = Depends(
        get_db,
    ),
) -> dict[str, Any]:
    """Return the foundational stats for one business."""

    await _require_business_ownership(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )

    stats = await (
        get_business_trend_foundation_stats(
            business_id,
        )
    )

    return {
        "business_id": str(
            stats.business_id,
        ),
        "total_posts": stats.total_posts,
        "total_post_metric_snapshots": (
            stats.total_post_metric_snapshots
        ),
        "total_comments": (
            stats.total_comments
        ),
        "total_customer_reviews": (
            stats.total_customer_reviews
        ),
        "posts_by_platform": (
            stats.posts_by_platform
        ),
        "comments_by_platform": (
            stats.comments_by_platform
        ),
        "reviews_by_source": (
            stats.reviews_by_source
        ),
    }


# ============================================================
# GET /businesses/{business_id}/trends/posts-per-week
# ============================================================
@router.get(
    (
        "/{business_id}/trends/"
        "posts-per-week"
    ),
    summary="Get posts per week trend",
)
async def read_posts_per_week_trend(
    business_id: UUID,
    range_start: datetime = Query(
        ...,
        description=(
            "Inclusive lower bound of "
            "published_at, UTC."
        ),
    ),
    range_end: datetime = Query(
        ...,
        description=(
            "Exclusive upper bound of "
            "published_at, UTC."
        ),
    ),
    current_user: User = Depends(
        get_current_user,
    ),
    db: AsyncSession = Depends(
        get_db,
    ),
) -> dict[str, Any]:
    """Return the posts-per-week trend for one business."""

    await _require_business_ownership(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )

    try:
        trend = await get_posts_per_week_trend(
            business_id=business_id,
            range_start=range_start,
            range_end=range_end,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(error),
        ) from error

    return {
        "business_id": str(
            trend.business_id,
        ),
        "range_start": (
            trend.range_start.isoformat()
        ),
        "range_end": (
            trend.range_end.isoformat()
        ),
        "total_posts": trend.total_posts,
        "buckets": [
            {
                "week_start": (
                    bucket.week_start.isoformat()
                ),
                "post_count": (
                    bucket.post_count
                ),
            }
            for bucket in trend.buckets
        ],
    }


# ============================================================
# GET /businesses/{business_id}/posts/{post_id}/engagement-curve
# ============================================================
@router.get(
    (
        "/{business_id}/posts/"
        "{social_post_id}/engagement-curve"
    ),
    summary=(
        "Get post engagement curve"
    ),
)
async def read_post_engagement_curve(
    business_id: UUID,
    social_post_id: PydanticObjectId,
    social_account_id: UUID = Query(
        ...,
        description=(
            "Owning social account id."
        ),
    ),
    range_start: datetime = Query(
        ...,
        description=(
            "Inclusive lower bound of "
            "captured_at, UTC."
        ),
    ),
    range_end: datetime = Query(
        ...,
        description=(
            "Exclusive upper bound of "
            "captured_at, UTC."
        ),
    ),
    current_user: User = Depends(
        get_current_user,
    ),
    db: AsyncSession = Depends(
        get_db,
    ),
) -> dict[str, Any]:
    """Return the daily engagement curve for one post."""

    await _require_business_ownership(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )

    try:
        curve = await get_post_engagement_curve(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=social_post_id,
            range_start=range_start,
            range_end=range_end,
        )
    except PostEngagementCurvePostNotFoundError:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Social post not found "
                "for this business and "
                "social account."
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(error),
        ) from error

    return {
        "business_id": str(
            curve.business_id,
        ),
        "social_account_id": str(
            curve.social_account_id,
        ),
        "social_post_id": str(
            curve.social_post_id,
        ),
        "range_start": (
            curve.range_start.isoformat()
        ),
        "range_end": (
            curve.range_end.isoformat()
        ),
        "points": [
            {
                "day": point.day.isoformat(),
                "captured_at": (
                    point.captured_at
                    .isoformat()
                ),
                "likes": point.likes,
                "reactions": point.reactions,
                "comments": point.comments,
                "shares": point.shares,
                "views": point.views,
            }
            for point in curve.points
        ],
    }


# ============================================================
# GET /businesses/{business_id}/trends/reviews-per-month
# ============================================================
@router.get(
    (
        "/{business_id}/trends/"
        "reviews-per-month"
    ),
    summary=(
        "Get reviews per month trend"
    ),
)
async def read_reviews_per_month_trend(
    business_id: UUID,
    range_start: datetime = Query(
        ...,
        description=(
            "Inclusive lower bound of "
            "published_at, UTC."
        ),
    ),
    range_end: datetime = Query(
        ...,
        description=(
            "Exclusive upper bound of "
            "published_at, UTC."
        ),
    ),
    source: str = Query(
        "google_maps",
        description=(
            "Customer voice source."
        ),
    ),
    current_user: User = Depends(
        get_current_user,
    ),
    db: AsyncSession = Depends(
        get_db,
    ),
) -> dict[str, Any]:
    """Return the reviews-per-month trend for one business."""

    await _require_business_ownership(
        db=db,
        business_id=business_id,
        owner_id=current_user.id,
    )

    try:
        trend = await (
            get_reviews_per_month_trend(
                business_id=business_id,
                range_start=range_start,
                range_end=range_end,
                source=source,
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(error),
        ) from error

    return {
        "business_id": str(
            trend.business_id,
        ),
        "source": trend.source,
        "range_start": (
            trend.range_start.isoformat()
        ),
        "range_end": (
            trend.range_end.isoformat()
        ),
        "total_reviews": (
            trend.total_reviews
        ),
        "total_meaningful_reviews": (
            trend.total_meaningful_reviews
        ),
        "buckets": [
            {
                "month_start": (
                    bucket.month_start
                    .isoformat()
                ),
                "review_count": (
                    bucket.review_count
                ),
                "meaningful_review_count": (
                    bucket
                    .meaningful_review_count
                ),
                "rating_average": (
                    bucket.rating_average
                ),
            }
            for bucket in trend.buckets
        ],
    }