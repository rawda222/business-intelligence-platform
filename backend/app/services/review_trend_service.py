"""
Review Trend Service

Provides tenant-scoped monthly review trends for stored customer
reviews.

Current trend:

- Reviews per month bucketed by published_at, normalized to UTC.
- Rating average per month, computed only from reviews carrying a
  numeric rating. Reviews without a rating do not contribute.
- Meaningful reviews per month, counted from reviews flagged as
  meaningful by the normalizer.

Empty months inside the requested range are still returned with
zero counts and a None rating average so downstream chart layers
can render a continuous timeline.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.schemas.normalized_social import (
    CustomerVoiceSource,
)


# ============================================================
# Result Dataclasses
# ============================================================
@dataclass(slots=True)
class ReviewsPerMonthBucket:
    """
    One monthly bucket in the reviews-per-month trend.

    month_start:
        UTC calendar date of the first day of the month.

    review_count:
        Total reviews published inside the month.

    meaningful_review_count:
        Reviews flagged as meaningful by the normalizer.

    rating_average:
        Mean of all numeric ratings inside the month.
        None when no rated review exists inside the month.
    """

    month_start: date

    review_count: int

    meaningful_review_count: int

    rating_average: float | None


@dataclass(slots=True)
class ReviewsPerMonthTrend:
    """
    Complete reviews-per-month trend for one business.
    """

    business_id: UUID

    source: CustomerVoiceSource

    range_start: datetime

    range_end: datetime

    buckets: list[
        ReviewsPerMonthBucket
    ]

    total_reviews: int

    total_meaningful_reviews: int


# ============================================================
# Range Helpers
# ============================================================
def _ensure_utc(
    value: datetime,
) -> datetime:
    """Return a UTC-aware datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )


def _first_day_of_month(
    value: datetime,
) -> date:
    """Return the UTC date of the first day of the month."""

    utc_value = _ensure_utc(
        value,
    )

    return date(
        utc_value.year,
        utc_value.month,
        1,
    )


def _next_month_start(
    value: date,
) -> date:
    """Return the first day of the following month."""

    if value.month == 12:
        return date(
            value.year + 1,
            1,
            1,
        )

    return date(
        value.year,
        value.month + 1,
        1,
    )


def _month_starts_within_range(
    range_start: datetime,
    range_end: datetime,
) -> list[date]:  # تم تصحيح الـ Type Hint وإضافة ":"
    """
    Return an ordered list of month start dates covering the range.
    """

    first_month = _first_day_of_month(
        range_start,
    )

    end_utc = _ensure_utc(
        range_end,
    )

    last_month = _first_day_of_month(
        datetime(
            end_utc.year,
            end_utc.month,
            end_utc.day,
            tzinfo=UTC,
        ),
    )

    # If range_end lands exactly on the start of the next month,
    # exclude that month because the range is end-exclusive.
    if (
        end_utc.day == 1
        and end_utc.hour == 0
        and end_utc.minute == 0
        and end_utc.second == 0
        and end_utc.microsecond == 0
    ):
        last_month_included = last_month

        last_month_included = date(
            last_month.year,
            last_month.month,
            1,
        )

        # Move one month back because that month has no coverage.
        if (
            last_month_included.year
            == last_month.year
            and last_month_included.month
            == last_month.month
        ):
            year = last_month.year
            month = last_month.month - 1

            if month == 0:
                month = 12
                year -= 1

            last_month = date(
                year,
                month,
                1,
            )

    months: list[date] = []

    current = first_month

    while current <= last_month:
        months.append(current)

        current = _next_month_start(
            current,
        )

    return months


# ============================================================
# Trend Query
# ============================================================
async def get_reviews_per_month_trend(
    *,
    business_id: UUID,
    range_start: datetime,
    range_end: datetime,
    source: CustomerVoiceSource = "google_maps",
) -> ReviewsPerMonthTrend:
    """
    Return the reviews-per-month trend for one business.

    The range filters published_at:
    - range_start is inclusive.
    - range_end is exclusive.

    Reviews without a numeric rating are excluded from the average
    computation but still counted in review_count.
    """

    if range_end <= range_start:
        raise ValueError(
            "range_end must be strictly "
            "greater than range_start."
        )

    normalized_start = _ensure_utc(
        range_start,
    )

    normalized_end = _ensure_utc(
        range_end,
    )

    matching_reviews = (
        CustomerReviewDocument.find(
            CustomerReviewDocument.business_id
            == business_id,
            CustomerReviewDocument.source
            == source,
            CustomerReviewDocument.published_at
            >= normalized_start,
            CustomerReviewDocument.published_at
            < normalized_end,
        )
    )

    counts_by_month: dict[date, int] = {}

    meaningful_by_month: dict[
        date,
        int,
    ] = {}

    rating_sum_by_month: dict[
        date,
        float,
    ] = {}

    rating_count_by_month: dict[
        date,
        int,
    ] = {}

    total_reviews = 0
    total_meaningful_reviews = 0

    async for review in matching_reviews:
        published_at = review.published_at

        if published_at is None:
            continue

        month_key = _first_day_of_month(
            published_at,
        )

        counts_by_month[month_key] = (
            counts_by_month.get(
                month_key,
                0,
            )
            + 1
        )

        total_reviews += 1

        if review.is_meaningful:
            meaningful_by_month[
                month_key
            ] = meaningful_by_month.get(
                month_key,
                0,
            ) + 1

            total_meaningful_reviews += 1

        rating = review.rating

        if rating is not None:
            rating_sum_by_month[
                month_key
            ] = rating_sum_by_month.get(
                month_key,
                0.0,
            ) + float(rating)

            rating_count_by_month[
                month_key
            ] = rating_count_by_month.get(
                month_key,
                0,
            ) + 1

    ordered_months = _month_starts_within_range(
        normalized_start,
        normalized_end,
    )

    buckets: list[
        ReviewsPerMonthBucket
    ] = []

    for month_start in ordered_months:
        review_count = counts_by_month.get(
            month_start,
            0,
        )

        meaningful_count = (
            meaningful_by_month.get(
                month_start,
                0,
            )
        )

        rating_sum = rating_sum_by_month.get(
            month_start,
            0.0,
        )

        rating_samples = (
            rating_count_by_month.get(
                month_start,
                0,
            )
        )

        rating_average = (
            rating_sum / rating_samples
            if rating_samples > 0
            else None
        )

        buckets.append(
            ReviewsPerMonthBucket(
                month_start=month_start,
                review_count=review_count,
                meaningful_review_count=(
                    meaningful_count
                ),
                rating_average=rating_average,
            )
        )

    return ReviewsPerMonthTrend(
        business_id=business_id,
        source=source,
        range_start=normalized_start,
        range_end=normalized_end,
        buckets=buckets,
        total_reviews=total_reviews,
        total_meaningful_reviews=(
            total_meaningful_reviews
        ),
    )