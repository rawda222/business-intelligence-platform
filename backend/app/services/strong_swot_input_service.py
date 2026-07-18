"""
Strong SWOT Input Service

Combines cross-source customer voice with deterministic business
trend intelligence into one evidence-controlled input bundle for
SWOT Agent v7.

Customer voice and brand activity remain separate:

- Google Maps reviews, Facebook comments, and Instagram comments
  are processed through the existing Theme Extractor.
- Brand-owned posts and engagement metrics remain trend evidence.
- Social posts are never treated as customer sentiment.

This service:

- Does not call an LLM.
- Does not write to MongoDB.
- Does not modify an existing SWOT.
- Rejects cross-business inputs.
- Preserves all allowed evidence references.
- Produces the exact BusinessProfile consumed by SWOT Agent v7.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.agents.swot.schemas.input import (
    BusinessProfile,
)
from app.preprocessing.theme_extractor.pipeline import (
    extract_themes,
)
from app.services.business_trend_intelligence_service import (
    BusinessTrendIntelligence,
)
from app.services.cross_source_customer_voice_service import (
    CrossSourceCustomerVoiceResult,
)
from app.services.swot_business_profile_builder import (
    build_swot_business_profile,
)
from app.services.swot_evidence_candidate_service import (
    SwotEvidenceCandidate,
    build_swot_evidence_candidates,
)


ThemeExtractor = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


@dataclass(frozen=True, slots=True)
class StrongSwotInputBundle:
    """
    Complete evidence-controlled input for Strong SWOT synthesis.

    The bundle contains both customer-voice themes and deterministic
    trend signals, but keeps their roles distinct.
    """

    business_id: UUID

    range_start: datetime

    range_end: datetime

    swot_profile: BusinessProfile

    themes_output: dict[str, Any]

    customer_voice: (
        CrossSourceCustomerVoiceResult
    )

    trend_intelligence: (
        BusinessTrendIntelligence
    )

    trend_candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ]

    allowed_evidence_references: tuple[
        str,
        ...
    ]

    source_coverage: tuple[
        str,
        ...
    ]

    warnings: tuple[
        str,
        ...
    ]


def _unique_strings(
    values: list[str],
) -> tuple[str, ...]:
    """Deduplicate non-empty strings while preserving order."""

    result: list[str] = []

    for value in values:
        if not isinstance(
            value,
            str,
        ):
            continue

        cleaned = value.strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    return tuple(
        result
    )


def _evidence_reference_string(
    value: Any,
) -> str | None:
    """Extract one explicit reference without inventing an ID."""

    if isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        return cleaned or None

    if isinstance(
        value,
        Mapping,
    ):
        for field_name in (
            "reference",
            "evidence_reference",
            "id",
            "review_id",
            "source_id",
        ):
            raw_reference = value.get(
                field_name
            )

            if isinstance(
                raw_reference,
                str,
            ):
                cleaned = (
                    raw_reference.strip()
                )

                if cleaned:
                    return cleaned

    return None


def _profile_evidence_references(
    profile: BusinessProfile,
) -> list[str]:
    """Collect evidence references from customer-voice themes."""

    references: list[str] = []

    for theme in profile.themes:
        for raw_reference in (
            theme.evidence_refs
        ):
            reference = (
                _evidence_reference_string(
                    raw_reference
                )
            )

            if (
                reference is not None
                and reference not in references
            ):
                references.append(
                    reference
                )

    return references


def _candidate_evidence_references(
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
) -> list[str]:
    """Collect deterministic trend evidence references."""

    references: list[str] = []

    for candidate in candidates:
        for reference in (
            candidate.evidence_references
        ):
            cleaned = reference.strip()

            if (
                cleaned
                and cleaned not in references
            ):
                references.append(
                    cleaned
                )

    return references


def _source_platform_to_coverage(
    source: str,
) -> str:
    """Convert theme platforms to the canonical coverage names."""

    if source == "google_maps":
        return "google_maps_reviews"

    return source


def _profile_source_coverage(
    profile: BusinessProfile,
) -> list[str]:
    """Collect canonical sources represented by customer themes."""

    sources: list[str] = []

    for theme in profile.themes:
        for source in (
            theme.source_platforms
        ):
            canonical_source = (
                _source_platform_to_coverage(
                    source
                )
            )

            if (
                canonical_source
                and canonical_source
                not in sources
            ):
                sources.append(
                    canonical_source
                )

    return sources


def _profile_source_coverage(
    profile: BusinessProfile,
) -> list[str]:
    """Collect canonical sources represented by customer themes."""

    sources: list[str] = []

    for theme in profile.themes:
        for source in theme.source_platforms:
            canonical_source = (
                _source_platform_to_coverage(
                    source
                )
            )

            if (
                canonical_source
                and canonical_source
                not in sources
            ):
                sources.append(
                    canonical_source
                )

    return sources


def _intelligence_source_coverage(
    intelligence: BusinessTrendIntelligence,
) -> list[str]:
    """Collect only sources observed by trend intelligence."""

    sources: list[str] = []

    for coverage in (
        intelligence.source_coverage
    ):
        if not coverage.available:
            continue

        source = coverage.source

        if source not in sources:
            sources.append(
                source
            )

    return sources


def _build_warnings(
    *,
    customer_voice: (
        CrossSourceCustomerVoiceResult
    ),
    intelligence: (
        BusinessTrendIntelligence
    ),
    profile: BusinessProfile,
    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ],
) -> tuple[str, ...]:
    """Build ordered warnings for downstream synthesis."""

    warnings: list[str] = []

    for warning in customer_voice.warnings:
        warnings.append(
            f"customer_voice:{warning}"
        )

    for warning in intelligence.warnings:
        warnings.append(
            f"trend_intelligence:{warning}"
        )

    if not customer_voice.business_reviews:
        warnings.append(
            "customer_voice:no_usable_records"
        )

    if not profile.themes:
        warnings.append(
            "theme_extractor:no_themes"
        )

    if not any(
        candidate.disposition
        == "swot_candidate"
        for candidate in candidates
    ):
        warnings.append(
            "trend_candidates:"
            "no_direct_swot_candidates"
        )

    return _unique_strings(
        warnings
    )


def build_strong_swot_input(
    *,
    customer_voice: (
        CrossSourceCustomerVoiceResult
    ),
    trend_intelligence: (
        BusinessTrendIntelligence
    ),
    theme_extractor: ThemeExtractor = (
        extract_themes
    ),
) -> StrongSwotInputBundle:
    """
    Build the complete input bundle for Strong SWOT synthesis.

    The resulting bundle is safe to pass to the later grounded LLM
    orchestration layer. The LLM output must reference only values
    contained in allowed_evidence_references.
    """

    if (
        customer_voice.business_id
        != trend_intelligence.business_id
    ):
        raise ValueError(
            "Customer voice business_id does not "
            "match trend intelligence business_id."
        )

    theme_input = (
        customer_voice
        .as_theme_extractor_input()
    )

    extracted_output = (
        theme_extractor(
            theme_input
        )
    )

    if not isinstance(
        extracted_output,
        Mapping,
    ):
        raise ValueError(
            "Theme Extractor must return a mapping."
        )

    themes_output = dict(
        extracted_output
    )

    profile = build_swot_business_profile(
        business_name=(
            customer_voice.business_name
        ),
        business_type=(
            customer_voice.business_type
        ),
        themes_output=themes_output,
        target_review_count=(
            customer_voice.records_included
        ),
    )

    candidates = (
        build_swot_evidence_candidates(
            trend_intelligence
        )
    )

    allowed_evidence_references = (
        _unique_strings(
            _profile_evidence_references(
                profile
            )
            + _candidate_evidence_references(
                candidates
            )
        )
    )

    source_coverage = (
        _unique_strings(
            _intelligence_source_coverage(
                trend_intelligence
            )
            + _profile_source_coverage(
                profile
            )
        )
    )

    warnings = _build_warnings(
        customer_voice=customer_voice,
        intelligence=trend_intelligence,
        profile=profile,
        candidates=candidates,
    )

    return StrongSwotInputBundle(
        business_id=(
            customer_voice.business_id
        ),
        range_start=(
            trend_intelligence.range_start
        ),
        range_end=(
            trend_intelligence.range_end
        ),
        swot_profile=profile,
        themes_output=themes_output,
        customer_voice=customer_voice,
        trend_intelligence=(
            trend_intelligence
        ),
        trend_candidates=candidates,
        allowed_evidence_references=(
            allowed_evidence_references
        ),
        source_coverage=(
            source_coverage
        ),
        warnings=warnings,
    )