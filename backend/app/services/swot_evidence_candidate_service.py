"""
SWOT Evidence Candidate Service

Converts business trend intelligence into conservative,
evidence-backed SWOT candidates.

This layer:

- Does not call an LLM.
- Does not modify the existing SWOT.
- Does not write to MongoDB.
- Does not invent opportunities or threats.
- Does not promote weak evidence to Strategy.
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

ClaimStrength = Literal[
    "validated",
    "internally_supported",
    "directional_not_validated",
    "early_warning",
]

CandidateDecision = Literal[
    "eligible",
    "manual_review",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class SwotEvidenceCandidate:
    """
    One evidence-backed assessment for later SWOT comparison.
    """

    candidate_id: str

    business_id: UUID

    disposition: CandidateDisposition

    quadrant: SwotQuadrant | None

    title: str

    statement: str

    rationale: str

    confidence: float

    claim_strength: ClaimStrength

    decision: CandidateDecision

    should_feed_strategy_agent: bool

    evidence_references: tuple[
        str,
        ...
    ]

    supporting_sources: tuple[
        TrendSource,
        ...
    ]

    supporting_metrics: tuple[
        tuple[str, float | int | str],
        ...
    ]

    mapping_rule: str

    requires_manual_review: bool


def _clamp_confidence(
    value: float,
) -> float:
    """Clamp confidence to the public zero-to-one range."""

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def _available_social_sources(
    intelligence: BusinessTrendIntelligence,
) -> tuple[
    TrendSource,
    ...
]:
    """Return social datasets observed in the report."""

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
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
) -> tuple[
    TrendSource,
    ...
]:
    """Return observed sources relevant to an evidence category."""

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


def _claim_policy(
    *,
    disposition: CandidateDisposition,
    confidence: float,
    source_count: int,
) -> tuple[
    ClaimStrength,
    CandidateDecision,
    bool,
]:
    """
    Apply the quality gate for downstream Strategy eligibility.
    """

    if disposition == "data_gap":
        return (
            "early_warning",
            "blocked",
            False,
        )

    if disposition == "supporting_signal":
        return (
            "directional_not_validated",
            "manual_review",
            False,
        )

    if (
        confidence >= 0.8
        and source_count >= 2
    ):
        return (
            "validated",
            "eligible",
            True,
        )

    if confidence >= 0.6:
        return (
            "internally_supported",
            "manual_review",
            False,
        )

    return (
        "directional_not_validated",
        "manual_review",
        False,
    )


def _candidate(
    *,
    intelligence: BusinessTrendIntelligence,
    evidence: TrendEvidence,
    disposition: CandidateDisposition,
    quadrant: SwotQuadrant | None,
    title: str,
    statement: str,
    rationale: str,
    mapping_rule: str,
) -> SwotEvidenceCandidate:
    """Build one quality-gated candidate."""

    sources = _sources_for_evidence(
        intelligence=intelligence,
        evidence=evidence,
    )

    confidence = _clamp_confidence(
        evidence.confidence
    )

    (
        claim_strength,
        decision,
        should_feed_strategy_agent,
    ) = _claim_policy(
        disposition=disposition,
        confidence=confidence,
        source_count=len(
            sources
        ),
    )

    suffix = (
        quadrant
        if quadrant is not None
        else disposition
    )

    return SwotEvidenceCandidate(
        candidate_id=(
            "trend:"
            f"{evidence.metric}:"
            f"{suffix}"
        ),
        business_id=(
            intelligence.business_id
        ),
        disposition=disposition,
        quadrant=quadrant,
        title=title,
        statement=statement,
        rationale=rationale,
        confidence=confidence,
        claim_strength=claim_strength,
        decision=decision,
        should_feed_strategy_agent=(
            should_feed_strategy_agent
        ),
        evidence_references=(
            evidence.reference,
        ),
        supporting_sources=sources,
        supporting_metrics=tuple(
            evidence.supporting_metrics.items()
        ),
        mapping_rule=mapping_rule,
        requires_manual_review=(
            decision != "eligible"
        ),
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
                title=(
                    "Social publishing data unavailable"
                ),
                statement=(
                    "No Facebook or Instagram publishing "
                    "records were observed in the selected "
                    "range."
                ),
                rationale=(
                    "Missing scraper records cannot support "
                    "a SWOT claim about publishing activity."
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
            title="No observed publishing activity",
            statement=(
                "No publishing activity was observed "
                "across the available social datasets "
                "in the selected range."
            ),
            rationale=(
                "Facebook or Instagram data were available, "
                "but the analyzed range contained no posts."
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
        title="Observed social publishing activity",
        statement=(
            "Social publishing activity was observed "
            "in the selected range."
        ),
        rationale=(
            "Post volume alone does not prove a Strength "
            "without directional or outcome evidence."
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
    """Classify the direction of publishing activity."""

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
            title="Increasing publishing activity",
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
            title="Declining publishing activity",
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
        title="Stable publishing activity",
        statement=(
            "Publishing activity remained stable "
            "during the selected range."
        ),
        rationale=(
            "Stable activity alone does not prove "
            "a Strength or Weakness."
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
    """Classify the observed customer-rating direction."""

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
            title="Improving customer ratings",
            statement=(
                "Customer rating averages improved "
                "during the selected range."
            ),
            rationale=(
                "The latest monthly rating average "
                "exceeded the earliest observed average."
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
            title="Declining customer ratings",
            statement=(
                "Customer rating averages declined "
                "during the selected range."
            ),
            rationale=(
                "The latest monthly rating average "
                "was below the earliest observed average."
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
        title="Stable customer ratings",
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
    """Treat low review volume as a data limitation."""

    total_reviews = int(
        evidence.value
    )

    if total_reviews < 5:
        return _candidate(
            intelligence=intelligence,
            evidence=evidence,
            disposition="data_gap",
            quadrant=None,
            title="Insufficient customer review volume",
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
        title="Customer review evidence available",
        statement=(
            "Customer review evidence is available "
            "for the selected range."
        ),
        rationale=(
            "Review volume supports rating-based claims "
            "but is not a SWOT item by itself."
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
    """Keep one observed engagement peak as support only."""

    return _candidate(
        intelligence=intelligence,
        evidence=evidence,
        disposition="supporting_signal",
        quadrant=None,
        title="Observed engagement peak",
        statement=(
            "A peak reaction count was observed "
            "across analyzed social posts."
        ),
        rationale=(
            "A single peak does not prove sustained "
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
    """Apply supported deterministic mapping rules."""

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
        title="Additional trend evidence",
        statement=evidence.description,
        rationale=(
            "No approved direct SWOT mapping rule "
            "exists for this metric."
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
    Build quality-gated SWOT candidates from trend evidence.

    Comparing these candidates against the existing SWOT is the
    responsibility of the later update-proposal service.
    """

    return tuple(
        _classify_evidence(
            intelligence=intelligence,
            evidence=evidence,
        )
        for evidence in intelligence.evidence
    )