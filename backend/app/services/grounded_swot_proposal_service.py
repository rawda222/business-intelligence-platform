"""
Grounded SWOT Proposal Service

Converts evidence-validated grounded SWOT items into the existing
SwotEvidenceCandidate contract, then builds a deterministic draft
SWOT update proposal against a normalized baseline.

The service:

- Accepts only items already accepted by the grounded validator.
- Rejects unsafe or cross-business generation results.
- Preserves evidence references and source coverage.
- Generates deterministic candidate IDs.
- Never routes draft proposal items directly to Strategy.
- Requires explicit human approval before Strategy eligibility.
- Does not write to MongoDB.
"""

from dataclasses import dataclass
from uuid import UUID, uuid5

from app.services.grounded_swot_generation_service import (
    GroundedSwotGenerationResult,
)
from app.services.grounded_swot_output_validator import (
    SafeGroundedSwotItem,
)
from app.services.legacy_swot_adapter import (
    NormalizedSwotBaseline,
)
from app.services.strong_swot_input_service import (
    StrongSwotInputBundle,
)
from app.services.swot_evidence_candidate_service import (
    SwotEvidenceCandidate,
)
from app.services.swot_update_proposal_service import (
    SwotUpdateProposal,
    build_swot_update_proposal,
    build_initial_swot_proposal,
)


_GROUNDED_CANDIDATE_NAMESPACE = UUID(
    "abababab-abab-abab-abab-abababababab"
)


_QUADRANT_MAP = {
    "strengths": "strength",
    "weaknesses": "weakness",
    "opportunities": "opportunity",
    "threats": "threat",
}


@dataclass(frozen=True, slots=True)
class GroundedSwotProposalResult:
    """Complete proposal result from grounded generation."""

    business_id: UUID

    generation: GroundedSwotGenerationResult

    candidates: tuple[
        SwotEvidenceCandidate,
        ...
    ]

    proposal: SwotUpdateProposal

    candidate_count: int

    requires_human_approval: bool

    safe_for_approval_workflow: bool

    warnings: tuple[
        str,
        ...
    ]


def _unique_strings(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    """Deduplicate non-empty strings while preserving order."""

    result: list[str] = []

    for value in values:
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


def _source_from_reference(
    reference: str,
) -> str | None:
    """Map one evidence reference to canonical source coverage."""

    prefix = reference.split(
        ":",
        maxsplit=1,
    )[0].strip().lower()

    if prefix == "google_maps":
        return "google_maps_reviews"

    if prefix in {
        "facebook",
        "instagram",
    }:
        return prefix

    return None


def _theme_sources(
    *,
    bundle: StrongSwotInputBundle,
    source_theme: str,
) -> tuple[str, ...]:
    """Return canonical sources from the matching customer theme."""

    theme = next(
        (
            value
            for value
            in bundle.swot_profile.themes
            if (
                value.theme_category
                == source_theme
            )
        ),
        None,
    )

    if theme is None:
        return ()

    sources: list[str] = []

    for platform in theme.source_platforms:
        if platform == "google_maps":
            source = "google_maps_reviews"
        else:
            source = platform

        if (
            source
            and source not in sources
        ):
            sources.append(
                source
            )

    return tuple(
        sources
    )


def _trend_sources(
    *,
    bundle: StrongSwotInputBundle,
    source_theme: str,
) -> tuple[str, ...]:
    """Return supporting sources from the exact trend candidate."""

    candidate = next(
        (
            value
            for value
            in bundle.trend_candidates
            if (
                value.candidate_id
                == source_theme
            )
        ),
        None,
    )

    if candidate is None:
        return ()

    return _unique_strings(
        tuple(
            str(source)
            for source
            in candidate.supporting_sources
        )
    )


def _supporting_sources(
    *,
    bundle: StrongSwotInputBundle,
    item: SafeGroundedSwotItem,
) -> tuple[str, ...]:
    """Resolve supporting sources without trusting the LLM."""

    if item.origin == "customer_theme":
        explicit_sources = _theme_sources(
            bundle=bundle,
            source_theme=item.source_theme,
        )
    else:
        explicit_sources = _trend_sources(
            bundle=bundle,
            source_theme=item.source_theme,
        )

    derived_sources = tuple(
        source
        for source in (
            _source_from_reference(
                reference
            )
            for reference
            in item.evidence_references
        )
        if source is not None
    )

    return _unique_strings(
        explicit_sources
        + derived_sources
    )


def _candidate_id(
    *,
    business_id: UUID,
    item: SafeGroundedSwotItem,
) -> str:
    """Build a deterministic candidate ID."""

    identity = "|".join(
        (
            str(
                business_id
            ),
            item.quadrant,
            item.source_theme,
            item.title.strip().lower(),
            ",".join(
                item.evidence_references
            ),
        )
    )

    generated_id = uuid5(
        _GROUNDED_CANDIDATE_NAMESPACE,
        identity,
    )

    return (
        "grounded:"
        f"{generated_id}"
    )


def _candidate_claim_strength(
    item: SafeGroundedSwotItem,
) -> str:
    """Map validator claim strength conservatively."""

    if item.claim_strength == "validated":
        return "validated"

    if (
        item.claim_strength
        == "internally_supported"
    ):
        return "directional"

    return "insufficient"


def _candidate_decision(
    item: SafeGroundedSwotItem,
) -> str:
    """Keep every generated candidate behind human review."""

    del item

    return "manual_review"


def _eligible_after_approval(
    item: SafeGroundedSwotItem,
) -> bool:
    """
    Return whether explicit human approval may enable Strategy use.

    A grounded item must have evidence and a usable confidence
    level. The draft itself still never feeds Strategy directly.
    """

    return bool(
        item.evidence_references
        and item.confidence >= 0.5
    )


def _to_candidate(
    *,
    business_id: UUID,
    bundle: StrongSwotInputBundle,
    item: SafeGroundedSwotItem,
) -> SwotEvidenceCandidate:
    """Convert one accepted grounded item to the existing contract."""

    quadrant = _QUADRANT_MAP.get(
        item.quadrant
    )

    if quadrant is None:
        raise ValueError(
            "Grounded SWOT item has an unsupported quadrant."
        )

    supporting_sources = (
        _supporting_sources(
            bundle=bundle,
            item=item,
        )
    )

    return SwotEvidenceCandidate(
        candidate_id=_candidate_id(
            business_id=business_id,
            item=item,
        ),
        business_id=business_id,
        disposition="swot_candidate",
        quadrant=quadrant,
        title=item.title,
        statement=item.reasoning,
        rationale=(
            "Generated by SWOT Agent v7 and accepted by "
            "the grounded evidence validator. "
            f"Source theme: {item.source_theme}."
        ),
        confidence=item.confidence,
        claim_strength=(
            _candidate_claim_strength(
                item
            )
        ),
        decision=_candidate_decision(
            item
        ),
        should_feed_strategy_agent=(
            _eligible_after_approval(
                item
            )
        ),
        evidence_references=(
            item.evidence_references
        ),
        supporting_sources=(
            supporting_sources
        ),
        supporting_metrics=(
            (
                "frequency",
                item.frequency,
            ),
            (
                "importance",
                item.importance,
            ),
            (
                "impact",
                item.impact,
            ),
            (
                "source_theme",
                item.source_theme,
            ),
            (
                "origin",
                item.origin,
            ),
        ),
        mapping_rule=(
            "grounded_llm_output_"
            "validated_against_evidence"
        ),
        requires_manual_review=True,
    )


def build_grounded_swot_update_proposal(
    *,
    baseline: NormalizedSwotBaseline,
    bundle: StrongSwotInputBundle,
    generation: GroundedSwotGenerationResult,
) -> GroundedSwotProposalResult:
    """
    Convert grounded generation into a draft update proposal.

    Only validation-accepted items are converted. Blocked or unsafe
    generation results are rejected before proposal creation.
    """

    if (
        baseline.business_id
        != bundle.business_id
    ):
        raise ValueError(
            "Strong SWOT bundle business_id does not "
            "match the baseline business_id."
        )

    if (
        generation.business_id
        != baseline.business_id
    ):
        raise ValueError(
            "Grounded generation business_id does not "
            "match the baseline business_id."
        )

    if not generation.safe_for_update_proposal:
        raise ValueError(
            "Grounded SWOT generation is not safe "
            "for an update proposal."
        )

    if generation.validation.blocked_items:
        raise ValueError(
            "Grounded SWOT generation contains "
            "blocked items."
        )

    if any(
        violation.severity == "error"
        for violation
        in generation.validation.violations
    ):
        raise ValueError(
            "Grounded SWOT generation contains "
            "evidence validation errors."
        )

    candidates = tuple(
        _to_candidate(
            business_id=baseline.business_id,
            bundle=bundle,
            item=item,
        )
        for item in generation.accepted_items
    )

    if not candidates:
        raise ValueError(
            "Grounded SWOT generation has no "
            "accepted items for proposal."
        )

    proposal = build_swot_update_proposal(
        baseline=baseline,
        candidates=candidates,
    )

    warnings = _unique_strings(
        generation.warnings
        + proposal.warnings
    )

    return GroundedSwotProposalResult(
        business_id=(
            baseline.business_id
        ),
        generation=generation,
        candidates=candidates,
        proposal=proposal,
        candidate_count=len(
            candidates
        ),
        requires_human_approval=(
            proposal
            .requires_human_approval
        ),
        safe_for_approval_workflow=bool(
            candidates
            and proposal.status
            == "draft"
            and proposal
            .requires_human_approval
        ),
        warnings=warnings,
    )

def build_grounded_swot_initial_proposal(
    *,
    bundle: StrongSwotInputBundle,
    generation: GroundedSwotGenerationResult,
) -> GroundedSwotProposalResult:
    """
    Build the first grounded SWOT proposal when no approved
    baseline exists.
    """

    # ✅ Validate business consistency
    if generation.business_id != bundle.business_id:
        raise ValueError(
            "Grounded generation business_id does not "
            "match the Strong SWOT bundle business_id."
        )

    # ✅ Safety checks
    if not generation.safe_for_update_proposal:
        raise ValueError(
            "Grounded SWOT generation is not safe "
            "for the approval workflow."
        )

    # ✅ Blocked items check
    if generation.validation.blocked_items:
        raise ValueError(
            "Grounded SWOT generation contains blocked items."
        )

    # ✅ Validation errors check
    if any(
        violation.severity == "error"
        for violation in generation.validation.violations
    ):
        raise ValueError(
            "Grounded SWOT generation contains "
            "evidence validation errors."
        )

    # ✅ Convert accepted items → candidates
    candidates = tuple(
        _to_candidate(
            business_id=bundle.business_id,
            bundle=bundle,
            item=item,
        )
        for item in generation.accepted_items
    )

    # ✅ Ensure we have candidates
    if not candidates:
        raise ValueError(
            "Grounded SWOT generation has no accepted "
            "items for an initial proposal."
        )

    # ✅ Build initial proposal
    proposal = build_initial_swot_proposal(
        business_id=bundle.business_id,
        candidates=candidates,
        source_coverage=tuple(
    bundle.swot_profile.source_coverage
),
    )

    # ✅ Merge warnings
    warnings = _unique_strings(
        generation.warnings
        + (
            "No approved SWOT baseline existed. "
            "This proposal creates the initial SWOT.",
        )
    )

    # ✅ Final result
    return GroundedSwotProposalResult(
        business_id=bundle.business_id,
        generation=generation,
        candidates=candidates,
        proposal=proposal,
        candidate_count=len(candidates),
        requires_human_approval=True,
        safe_for_approval_workflow=bool(
            candidates
            and proposal.status == "draft"
            and proposal.requires_human_approval
        ),
        warnings=warnings,
    )