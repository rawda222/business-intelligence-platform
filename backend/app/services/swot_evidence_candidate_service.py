"""
SWOT Evidence Candidate Service

Converts business trend evidence into conservative SWOT candidate
assessments.

The service does not compare against an existing SWOT, call an
LLM, or write to a database. It only classifies supported trend
signals for the later SWOT update-proposal layer.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.services.business_trend_intelligence_service import (
    BusinessTrendIntelligence,
    TrendSource,
)
from app.services.trend_evidence_service import (
    TrendEvidence,
)


SwotQuadrant = Literal[
    "strength",
    "weakness",
    "opportunity",
    "threat",
]


CandidateDisposition = Literal[
    "swot_candidate",
    "supporting_signal",
    "data_gap",
]


@dataclass(frozen=True, slots=True)
class SwotEvidenceCandidate:
    """One evidence-backed assessment for SWOT proposal building."""

    candidate_id: str

    business_id: UUID

    disposition: CandidateDisposition

    quadrant: SwotQuadrant | None

    statement: str

    rationale: str

    confidence: float

    evidence_references: tuple[
        str,
        ...
    ]

    supporting_sources: tuple[
        TrendSource,
        ...
    ]

    mapping_rule: str

    requires_manual_review: bool = True


def _available_social_sources(
    intelligence: BusinessTrendIntelligence,
) -> tuple[
    TrendSource,
    ...
]:
    """Return observed social datasets in deterministic order."""

    return tuple(
        coverage.source
        for coverage in intelligence.source_coverage
        if (
            coverage.available
            and coverage.source
            in (
                "facebook",
                "instagram",
            )
        )
    )


def _sources_for_evidence(
    *,
    evidence: TrendEvidence,
    intelligence: BusinessTrendIntelligence,
) -> tuple[
    TrendSource,
    ...
]:
    """Return source coverage relevant to one evidence category."""

    if evidence.category == "reviews":
        return tuple(
            coverage.source
            for coverage in intelligence.source_coverage
            if (
                coverage.available
                and coverage.source
                == "google_maps_reviews"
            )
        )

    if evidence.category in (
        "publishing",
        "engagement",
    ):
        return _available_social_sources(
            intelligence
        )

    return ()


def _candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
    disposition: CandidateDisposition,
    quadrant: SwotQuadrant | None,
    statement: str,
    rationale: str,
    mapping_rule: str,
) -> SwotEvidenceCandidate:
    """Build one deterministic candidate."""

    candidate_suffix = (
        quadrant
        if quadrant is not None
        else disposition
    )

    return SwotEvidenceCandidate(
        candidate_id=(
            "trend:"
            f"{evidence.metric}:"
            f"{candidate_suffix}"
        ),
        business_id=(
            intelligence.business_id
        ),
        disposition=disposition,
        quadrant=quadrant,
        statement=statement,
        rationale=rationale,
        confidence=max(
            0.0,
            min(
                1.0,
                evidence.confidence,
            ),
        ),
        evidence_references=(
            evidence.reference,
        ),
        supporting_sources=(
            _sources_for_evidence(
                evidence=evidence,
                intelligence=intelligence,
            )
        ),
        mapping_rule=mapping_rule,
        requires_manual_review=True,
    )


def _publishing_activity_candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Classify total publishing activity."""

    total_posts = int(
        evidence.value
    )

    social_sources = (
        _available_social_sources(
            intelligence
        )
    )

    if total_posts == 0:
        if not social_sources:
            return _candidate(
                intelligence=intelligence,
                evidence=evidence,
                disposition="data_gap",
                quadrant=None,
                statement=(
                    "No social publishing dataset "
                    "was observed in the selected range."
                ),
                rationale=(
                    "Missing Facebook and Instagram "
                    "records cannot support a SWOT "
                    "claim about publishing performance."
                ),
                mapping_rule=(
                    "missing_social_data_to_gap_v1"
                ),
            )

        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="swot_candidate",
            quadrant="weakness",
            statement=(
                "No publishing activity was observed "
                "across the available social datasets "
                "in the selected range."
            ),
            rationale=(
                "Observed social datasets were available, "
                "but the trend report contained no posts."
            ),
            mapping_rule=(
                "zero_publishing_to_weakness_v1"
            ),
        )

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=(
            "Publishing activity was observed "
            "in the selected range."
        ),
        rationale=(
            "Post volume alone does not establish "
            "a business strength without direction "
            "or outcome evidence."
        ),
        mapping_rule=(
            "publishing_activity_to_support_v1"
        ),
    )


def _publishing_direction_candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Classify publishing direction using explicit bucket totals."""

    first_total = int(
        evidence.supporting_metrics.get(
            "first_half_posts",
            0,
        )
    )

    second_total = int(
        evidence.supporting_metrics.get(
            "second_half_posts",
            0,
        )
    )

    if second_total > first_total:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="swot_candidate",
            quadrant="strength",
            statement=(
                "Publishing activity increased "
                "during the selected range."
            ),
            rationale=(
                "The second half contained more "
                "published posts than the first half."
            ),
            mapping_rule=(
                "publishing_growth_to_strength_v1"
            ),
        )

    if second_total < first_total:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="swot_candidate",
            quadrant="weakness",
            statement=(
                "Publishing activity decreased "
                "during the selected range."
            ),
            rationale=(
                "The second half contained fewer "
                "published posts than the first half."
            ),
            mapping_rule=(
                "publishing_decline_to_weakness_v1"
            ),
        )

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=(
            "Publishing activity remained stable "
            "during the selected range."
        ),
        rationale=(
            "Stable activity alone does not establish "
            "a SWOT strength or weakness."
        ),
        mapping_rule=(
            "stable_publishing_to_support_v1"
        ),
    )


def _rating_direction_candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Classify customer-rating direction."""

    first_average = float(
        evidence.supporting_metrics.get(
            "first_month_rating_average",
            0.0,
        )
    )

    last_average = float(
        evidence.supporting_metrics.get(
            "last_month_rating_average",
            0.0,
        )
    )

    if last_average > first_average:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="swot_candidate",
            quadrant="strength",
            statement=(
                "Customer rating averages improved "
                "during the selected range."
            ),
            rationale=(
                "The latest observed monthly rating "
                "average exceeded the earliest one."
            ),
            mapping_rule=(
                "rating_improvement_to_strength_v1"
            ),
        )

    if last_average < first_average:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="swot_candidate",
            quadrant="weakness",
            statement=(
                "Customer rating averages declined "
                "during the selected range."
            ),
            rationale=(
                "The latest observed monthly rating "
                "average was below the earliest one."
            ),
            mapping_rule=(
                "rating_decline_to_weakness_v1"
            ),
        )

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=(
            "Customer rating averages remained stable."
        ),
        rationale=(
            "No directional rating change was observed."
        ),
        mapping_rule=(
            "stable_rating_to_support_v1"
        ),
    )


def _review_volume_candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Treat low review volume as a data-quality limitation."""

    total_reviews = int(
        evidence.value
    )

    if total_reviews < 5:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="data_gap",
            quadrant=None,
            statement=(
                "Customer review volume is too low "
                "for a reliable SWOT conclusion."
            ),
            rationale=(
                "Fewer than five reviews were observed "
                "in the selected range."
            ),
            mapping_rule=(
                "low_review_volume_to_gap_v1"
            ),
        )

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=(
            "Customer review evidence is available "
            "for the selected range."
        ),
        rationale=(
            "Review volume supports other review-based "
            "signals but is not a SWOT item by itself."
        ),
        mapping_rule=(
            "review_volume_to_support_v1"
        ),
    )


def _engagement_candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Keep peak reactions as supporting evidence only."""

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=(
            "A peak reaction count was observed "
            "across analyzed posts."
        ),
        rationale=(
            "A single peak does not establish sustained "
            "engagement or platform superiority."
        ),
        mapping_rule=(
            "peak_reactions_to_support_v1"
        ),
    )


def _classify_evidence(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> SwotEvidenceCandidate:
    """Apply the supported deterministic mapping rules."""

    if evidence.metric == "total_posts":
        return _publishing_activity_candidate(
            intelligence=intelligence,
            evidence=evidence,
        )

    if (
        evidence.metric
        == "publishing_trend_direction"
    ):
        return _publishing_direction_candidate(
            intelligence=intelligence,
            evidence=evidence,
        )

    if (
        evidence.metric
        == "rating_average_direction"
    ):
        return _rating_direction_candidate(
            intelligence=intelligence,
            evidence=evidence,
        )

    if evidence.metric == "total_reviews":
        return _review_volume_candidate(
            intelligence=intelligence,
            evidence=evidence,
        )

    if (
        evidence.metric
        == "peak_reactions_observed"
    ):
        return _engagement_candidate(
            intelligence=intelligence,
            evidence=evidence,
        )

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        statement=evidence.description,
        rationale=(
            "No direct SWOT mapping rule exists "
            "for this evidence metric."
        ),
        mapping_rule=(
            "unmapped_evidence_to_support_v1"
        ),
    )


def build_swot_evidence_candidates(
    intelligence: BusinessTrendIntelligence,
) -> tuple[
    SwotEvidenceCandidate,
    ...
]:
    """
    Build ordered SWOT assessments from business trend evidence.

    The output is not a SWOT update proposal. Comparing candidates
    with an existing SWOT is handled by the next service layer.
    """

    return tuple(
        _classify_evidence(
            intelligence=intelligence,
            evidence=evidence,
        )
        for evidence in intelligence.evidence
    )