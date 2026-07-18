"""
Business Trend Intelligence Service

Combines one business-scoped trend report with deterministic
insights, structured evidence, source coverage, and data-quality
warnings.

The service does not query databases and does not call an LLM.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.services.business_trend_report_service import (
    BusinessTrendReport,
)
from app.services.trend_evidence_service import (
    TrendEvidence,
    build_trend_evidence,
)
from app.services.trend_insight_service import (
    TrendInsight,
    build_trend_insights,
)


TrendSource = Literal[
    "business_profile",
    "google_maps_reviews",
    "facebook",
    "instagram",
]


LEGACY_SWOT_SOURCES: tuple[
    TrendSource,
    ...
] = (
    "business_profile",
    "google_maps_reviews",
)


@dataclass(frozen=True, slots=True)
class TrendSourceCoverage:
    """Observed data coverage for one intelligence source."""

    source: TrendSource

    available: bool

    post_count: int = 0

    comment_count: int = 0

    review_count: int = 0

    references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessTrendIntelligence:
    """Complete deterministic intelligence for one business."""

    business_id: UUID

    range_start: datetime

    range_end: datetime

    report: BusinessTrendReport

    insights: tuple[
        TrendInsight,
        ...
    ]

    evidence: tuple[
        TrendEvidence,
        ...
    ]

    source_coverage: tuple[
        TrendSourceCoverage,
        ...
    ]

    baseline_sources: tuple[
        TrendSource,
        ...
    ]

    new_sources_since_baseline: tuple[
        TrendSource,
        ...
    ]

    warnings: tuple[str, ...]


def _count_for_key(
    values: dict[str, int],
    key: str,
) -> int:
    """Return one normalized non-negative count."""

    value = values.get(
        key,
        0,
    )

    if value < 0:
        return 0

    return value


def _build_source_coverage(
    report: BusinessTrendReport,
) -> tuple[
    TrendSourceCoverage,
    ...
]:
    """Build coverage from records observed in the report."""

    foundation = report.foundation

    google_review_count = _count_for_key(
        foundation.reviews_by_source,
        "google_maps",
    )

    facebook_post_count = _count_for_key(
        foundation.posts_by_platform,
        "facebook",
    )

    facebook_comment_count = _count_for_key(
        foundation.comments_by_platform,
        "facebook",
    )

    instagram_post_count = _count_for_key(
        foundation.posts_by_platform,
        "instagram",
    )

    instagram_comment_count = _count_for_key(
        foundation.comments_by_platform,
        "instagram",
    )

    return (
        TrendSourceCoverage(
            source="business_profile",
            available=True,
            references=(
                (
                    "business-profile:"
                    f"{report.business_id}"
                ),
            ),
        ),
        TrendSourceCoverage(
            source="google_maps_reviews",
            available=(
                google_review_count > 0
            ),
            review_count=(
                google_review_count
            ),
            references=(
                "reviews_by_source:google_maps",
            ),
        ),
        TrendSourceCoverage(
            source="facebook",
            available=(
                facebook_post_count > 0
                or facebook_comment_count > 0
            ),
            post_count=(
                facebook_post_count
            ),
            comment_count=(
                facebook_comment_count
            ),
            references=(
                "posts_by_platform:facebook",
                "comments_by_platform:facebook",
            ),
        ),
        TrendSourceCoverage(
            source="instagram",
            available=(
                instagram_post_count > 0
                or instagram_comment_count > 0
            ),
            post_count=(
                instagram_post_count
            ),
            comment_count=(
                instagram_comment_count
            ),
            references=(
                "posts_by_platform:instagram",
                "comments_by_platform:instagram",
            ),
        ),
    )


def _build_warnings(
    source_coverage: tuple[
        TrendSourceCoverage,
        ...
    ],
) -> tuple[str, ...]:
    """Build data-quality warnings without inventing evidence."""

    coverage_by_source = {
        entry.source: entry
        for entry in source_coverage
    }

    warnings: list[str] = []

    if not coverage_by_source[
        "google_maps_reviews"
    ].available:
        warnings.append(
            "No Google Maps review records "
            "were observed in the report range."
        )

    if not coverage_by_source[
        "facebook"
    ].available:
        warnings.append(
            "No Facebook post or comment "
            "records were observed in the "
            "report range."
        )

    if not coverage_by_source[
        "instagram"
    ].available:
        warnings.append(
            "No Instagram post or comment "
            "records were observed in the "
            "report range."
        )

    return tuple(
        warnings
    )


def build_business_trend_intelligence(
    report: BusinessTrendReport,
    baseline_sources: tuple[
        TrendSource,
        ...
    ] = LEGACY_SWOT_SOURCES,
) -> BusinessTrendIntelligence:
    """
    Build intelligence and source delta for one trend report.

    Source availability means that records from the source were
    observed in the report. A connected social account alone is
    not treated as trend-data coverage.
    """

    insights = tuple(
        build_trend_insights(
            report
        )
    )

    evidence = tuple(
        build_trend_evidence(
            report=report,
            insights=list(
                insights
            ),
        )
    )

    source_coverage = (
        _build_source_coverage(
            report
        )
    )


    baseline_source_set = set(
        baseline_sources
    )

    new_sources = tuple(
        entry.source
        for entry in source_coverage
        if (
            entry.available
            and entry.source
            not in baseline_source_set
        )
    )

    warnings = _build_warnings(
        source_coverage
    )

    return BusinessTrendIntelligence(
        business_id=report.business_id,
        range_start=report.range_start,
        range_end=report.range_end,
        report=report,
        insights=insights,
        evidence=evidence,
        source_coverage=(
            source_coverage
        ),
        baseline_sources=(
            baseline_sources
        ),
        new_sources_since_baseline=(
            new_sources
        ),
        warnings=warnings,
    )