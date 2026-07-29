"""
Grounded SWOT Output Validator

Validates and safely reconstructs SWOT items produced by an LLM.

The validator treats the LLM output as untrusted input.

The LLM may suggest:

- title
- reasoning
- tags
- scores

Python controls:

- source-theme validity
- quadrant eligibility
- evidence references
- frequency
- confidence ceiling
- claim strength
- manual-review state
- Strategy routing

No accepted item is routed directly to Strategy. Human approval is
still required after grounded validation.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.services.strong_swot_input_service import (
    StrongSwotInputBundle,
)


GroundedQuadrant = Literal[
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
]

ViolationSeverity = Literal[
    "error",
    "warning",
]

GroundedItemOrigin = Literal[
    "customer_theme",
    "trend_candidate",
]


_QUADRANTS: tuple[GroundedQuadrant, ...] = (
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
)

_TREND_QUADRANT_MAP = {
    "strength": "strengths",
    "strengths": "strengths",
    "weakness": "weaknesses",
    "weaknesses": "weaknesses",
    "opportunity": "opportunities",
    "opportunities": "opportunities",
    "threat": "threats",
    "threats": "threats",
}


@dataclass(frozen=True, slots=True)
class GroundedSwotViolation:
    """One deterministic validation violation."""

    code: str

    severity: ViolationSeverity

    quadrant: str | None

    item_title: str | None

    source_theme: str | None

    invalid_references: tuple[str, ...]

    message: str


@dataclass(frozen=True, slots=True)
class SafeGroundedSwotItem:
    """One evidence-validated SWOT item."""

    quadrant: GroundedQuadrant

    title: str

    reasoning: str

    source_theme: str

    tags: tuple[str, ...]

    importance: float

    impact: float

    confidence: float

    frequency: int

    evidence_references: tuple[str, ...]

    origin: GroundedItemOrigin

    claim_strength: str

    requires_manual_review: bool

    should_feed_strategy_agent: bool


@dataclass(frozen=True, slots=True)
class BlockedGroundedSwotItem:
    """One rejected LLM SWOT item."""

    quadrant: str

    title: str

    source_theme: str

    evidence_references: tuple[str, ...]

    violation_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundedSwotValidationResult:
    """Complete deterministic validation result."""

    business_id: Any

    valid: bool

    accepted_items: tuple[
        SafeGroundedSwotItem,
        ...
    ]

    blocked_items: tuple[
        BlockedGroundedSwotItem,
        ...
    ]

    violations: tuple[
        GroundedSwotViolation,
        ...
    ]

    allowed_evidence_references: tuple[str, ...]

    observed_evidence_references: tuple[str, ...]

    requires_human_review: bool


def _get_value(
    value: Any,
    field_name: str,
    default: Any = None,
) -> Any:
    """Read one field from a mapping or object."""

    if isinstance(
        value,
        Mapping,
    ):
        return value.get(
            field_name,
            default,
        )

    return getattr(
        value,
        field_name,
        default,
    )


def _as_mapping(
    value: Any,
) -> dict[str, Any]:
    """Convert supported model-like values to a mapping."""

    if isinstance(
        value,
        Mapping,
    ):
        return dict(
            value
        )

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(
        model_dump
    ):
        dumped = model_dump()

        if isinstance(
            dumped,
            Mapping,
        ):
            return dict(
                dumped
            )

    return {}


def _as_list(
    value: Any,
) -> list[Any]:
    """Return list-like values without inventing entries."""

    if isinstance(
        value,
        list,
    ):
        return list(
            value
        )

    if isinstance(
        value,
        tuple,
    ):
        return list(
            value
        )

    return []


def _clean_text(
    value: Any,
) -> str:
    """Return stripped text or an empty string."""

    if not isinstance(
        value,
        str,
    ):
        return ""

    return value.strip()


def _unique_strings(
    values: list[Any],
) -> tuple[str, ...]:
    """Normalize and deduplicate strings in source order."""

    result: list[str] = []

    for value in values:
        cleaned = _clean_text(
            value
        )

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


def _bounded_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
) -> float:
    """Convert and clamp one numeric value."""

    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        normalized = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    return max(
        minimum,
        min(
            maximum,
            normalized,
        ),
    )


def _non_negative_int(
    value: Any,
    *,
    default: int = 0,
) -> int:
    """Convert one value to a non-negative integer."""

    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        normalized = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    return max(
        0,
        normalized,
    )


def _candidate_id(
    candidate: Any,
) -> str:
    """Return one exact trend-candidate ID."""

    return _clean_text(
        _get_value(
            candidate,
            "candidate_id",
        )
    )


def _candidate_references(
    candidate: Any,
) -> tuple[str, ...]:
    """Return the evidence IDs belonging to one trend candidate."""

    return _unique_strings(
        _as_list(
            _get_value(
                candidate,
                "evidence_references",
                (),
            )
        )
    )


def _theme_references(
    theme: Any,
) -> tuple[str, ...]:
    """Return the evidence IDs belonging to one customer theme."""

    return _unique_strings(
        _as_list(
            _get_value(
                theme,
                "evidence_refs",
                (),
            )
        )
    )


def _theme_confidence(
    theme: Any,
) -> float:
    """Return the evidence confidence ceiling for one theme."""

    raw_confidence = _get_value(
        theme,
        "confidence_score",
    )

    if raw_confidence is None:
        return 0.5

    return _bounded_float(
        raw_confidence,
        minimum=0.0,
        maximum=1.0,
        default=0.5,
    )


def _theme_frequency(
    theme: Any,
) -> int:
    """Return the authoritative theme frequency."""

    return _non_negative_int(
        _get_value(
            theme,
            "frequency",
            0,
        )
    )


def _theme_allowed_quadrants(
    theme: Any,
) -> tuple[GroundedQuadrant, ...]:
    """
    Derive allowed quadrants from deterministic theme evidence.

    Target-business themes:
    - Positive dominant -> Strength.
    - Negative dominant -> Weakness.

    Comparative themes:
    - Positive performance gap -> Opportunity.
    - Negative performance gap -> Threat.
    """

    entity_type = _clean_text(
        _get_value(
            theme,
            "entity_type",
        )
    )

    if entity_type == "target_business":
        sentiment = _get_value(
            theme,
            "sentiment_balance",
        )

        positive = _non_negative_int(
            _get_value(
                sentiment,
                "positive",
                0,
            )
        )

        negative = _non_negative_int(
            _get_value(
                sentiment,
                "negative",
                0,
            )
        )

        if (
            positive > negative
            and positive > 0
        ):
            return (
                "strengths",
                "opportunities",
            )

        if (
            negative > positive
            and negative > 0
        ):
            return (
                "weaknesses",
                "threats",
            )

        return ()

    if entity_type == "comparative":
        raw_gap = _get_value(
            theme,
            "performance_gap",
        )

        if raw_gap is None:
            return ()

        try:
            gap = float(
                raw_gap
            )
        except (
            TypeError,
            ValueError,
        ):
            return ()

        if gap > 0.15:
            return (
                "opportunities",
            )

        if gap < -0.15:
            return (
                "threats",
            )

    return ()


def _trend_allowed_quadrant(
    candidate: Any,
) -> GroundedQuadrant | None:
    """Return the canonical quadrant of one trend candidate."""

    raw_quadrant = _clean_text(
        _get_value(
            candidate,
            "quadrant",
        )
    ).lower()

    canonical = _TREND_QUADRANT_MAP.get(
        raw_quadrant
    )

    if canonical in _QUADRANTS:
        return canonical

    return None


def _candidate_is_actionable(
    candidate: Any,
) -> bool:
    """Return whether a trend candidate may support a SWOT item."""

    disposition = _clean_text(
        _get_value(
            candidate,
            "disposition",
        )
    )

    if disposition != "swot_candidate":
        return False

    decision = _clean_text(
        _get_value(
            candidate,
            "decision",
        )
    )

    return decision in {
        "eligible",
        "manual_review",
    }


def _candidate_confidence(
    candidate: Any,
) -> float:
    """Return a trend candidate confidence ceiling."""

    return _bounded_float(
        _get_value(
            candidate,
            "confidence",
            0.5,
        ),
        minimum=0.0,
        maximum=1.0,
        default=0.5,
    )


def _candidate_claim_strength(
    candidate: Any,
) -> str:
    """Return candidate claim strength conservatively."""

    claim_strength = _clean_text(
        _get_value(
            candidate,
            "claim_strength",
        )
    )

    return (
        claim_strength
        or "manual_review_only"
    )


def _candidate_requires_review(
    candidate: Any,
) -> bool:
    """Return whether deterministic gates require manual review."""

    if bool(
        _get_value(
            candidate,
            "requires_manual_review",
            False,
        )
    ):
        return True

    return (
        _clean_text(
            _get_value(
                candidate,
                "decision",
            )
        )
        != "eligible"
    )


def _extract_report(
    llm_output: Any,
) -> dict[str, Any]:
    """Extract the SWOT report from supported LLM output shapes."""

    output = _as_mapping(
        llm_output
    )

    report = _as_mapping(
        output.get(
            "swot_report"
        )
    )

    if report:
        return report

    swot = _as_mapping(
        output.get(
            "swot"
        )
    )

    if swot:
        return swot

    if any(
        quadrant in output
        for quadrant in _QUADRANTS
    ):
        return output

    return {}


def _scoring(
    item: dict[str, Any],
) -> dict[str, Any]:
    """Return one LLM scoring block."""

    return _as_mapping(
        item.get(
            "scoring"
        )
    )


def _violation(
    *,
    code: str,
    quadrant: str | None,
    title: str | None,
    source_theme: str | None,
    message: str,
    invalid_references: tuple[
        str,
        ...
    ] = (),
    severity: ViolationSeverity = "error",
) -> GroundedSwotViolation:
    """Build one validation violation."""

    return GroundedSwotViolation(
        code=code,
        severity=severity,
        quadrant=quadrant,
        item_title=title,
        source_theme=source_theme,
        invalid_references=(
            invalid_references
        ),
        message=message,
    )


def validate_grounded_swot_output(
    *,
    bundle: StrongSwotInputBundle,
    llm_output: Any,
) -> GroundedSwotValidationResult:
    """
    Validate and safely reconstruct one untrusted LLM SWOT output.

    Items containing any error-level violation are blocked.
    Accepted items remain subject to human approval and therefore
    never feed Strategy directly from this validation stage.
    """

    allowed_global = set(
        bundle.allowed_evidence_references
    )

    themes_by_category = {
        theme.theme_category: theme
        for theme in (
            bundle
            .swot_profile
            .themes
        )
    }

    candidates_by_id = {
        _candidate_id(
            candidate
        ): candidate
        for candidate in (
            bundle.trend_candidates
        )
        if _candidate_id(
            candidate
        )
    }

    report = _extract_report(
        llm_output
    )

    accepted: list[
        SafeGroundedSwotItem
    ] = []

    blocked: list[
        BlockedGroundedSwotItem
    ] = []

    violations: list[
        GroundedSwotViolation
    ] = []

    observed_references: list[str] = []

    if not report:
        violations.append(
            _violation(
                code="missing_swot_report",
                quadrant=None,
                title=None,
                source_theme=None,
                message=(
                    "The LLM output does not contain "
                    "a usable SWOT report."
                ),
            )
        )

    for quadrant in _QUADRANTS:
        raw_items = _as_list(
            report.get(
                quadrant,
                []
            )
        )

        for raw_item in raw_items:
            item = _as_mapping(
                raw_item
            )

            title = _clean_text(
                item.get(
                    "title"
                )
            )

            reasoning = _clean_text(
                item.get(
                    "reasoning"
                )
            )

            source_theme = _clean_text(
                item.get(
                    "source_theme"
                )
            )

            references = _unique_strings(
                _as_list(
                    item.get(
                        "evidence_refs"
                    )
                )
            )

            for reference in references:
                if (
                    reference
                    not in observed_references
                ):
                    observed_references.append(
                        reference
                    )

            item_violations: list[
                GroundedSwotViolation
            ] = []

            if not title:
                item_violations.append(
                    _violation(
                        code="missing_title",
                        quadrant=quadrant,
                        title=None,
                        source_theme=(
                            source_theme
                            or None
                        ),
                        message=(
                            "The SWOT item has no title."
                        ),
                    )
                )

            if not reasoning:
                item_violations.append(
                    _violation(
                        code="missing_reasoning",
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=(
                            source_theme
                            or None
                        ),
                        message=(
                            "The SWOT item has no reasoning."
                        ),
                    )
                )

            if not source_theme:
                item_violations.append(
                    _violation(
                        code="missing_source_theme",
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=None,
                        message=(
                            "The SWOT item has no source_theme."
                        ),
                    )
                )

            if not references:
                item_violations.append(
                    _violation(
                        code="missing_evidence",
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=(
                            source_theme
                            or None
                        ),
                        message=(
                            "The SWOT item has no "
                            "evidence references."
                        ),
                    )
                )

            unknown_global_references = tuple(
                reference
                for reference in references
                if (
                    reference
                    not in allowed_global
                )
            )

            if unknown_global_references:
                item_violations.append(
                    _violation(
                        code=(
                            "unknown_evidence_reference"
                        ),
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=(
                            source_theme
                            or None
                        ),
                        invalid_references=(
                            unknown_global_references
                        ),
                        message=(
                            "The SWOT item uses evidence "
                            "outside the allowed evidence "
                            "reference list."
                        ),
                    )
                )

            theme = themes_by_category.get(
                source_theme
            )

            candidate = candidates_by_id.get(
                source_theme
            )

            authoritative_references: tuple[
                str,
                ...
            ] = ()

            authoritative_frequency = 0

            confidence_ceiling = 0.5

            origin: GroundedItemOrigin = (
                "customer_theme"
            )

            claim_strength = (
                "manual_review_only"
            )

            requires_manual_review = True

            if theme is not None:
                authoritative_references = (
                    _theme_references(
                        theme
                    )
                )

                authoritative_frequency = (
                    _theme_frequency(
                        theme
                    )
                )

                confidence_ceiling = (
                    _theme_confidence(
                        theme
                    )
                )

                allowed_quadrants = (
                    _theme_allowed_quadrants(
                        theme
                    )
                )

                if quadrant not in allowed_quadrants:
                    item_violations.append(
                        _violation(
                            code=(
                                "incompatible_theme_quadrant"
                            ),
                            quadrant=quadrant,
                            title=title or None,
                            source_theme=source_theme,
                            message=(
                                "The customer theme does not "
                                "support the requested SWOT "
                                "quadrant."
                            ),
                        )
                    )

                claim_strength = (
                    "internally_supported"
                    if (
                        confidence_ceiling
                        >= 0.7
                        and authoritative_references
                    )
                    else "manual_review_only"
                )

            elif candidate is not None:
                origin = "trend_candidate"

                if not _candidate_is_actionable(
                    candidate
                ):
                    item_violations.append(
                        _violation(
                            code=(
                                "non_actionable_trend_candidate"
                            ),
                            quadrant=quadrant,
                            title=title or None,
                            source_theme=source_theme,
                            message=(
                                "The trend candidate is a "
                                "supporting signal, data gap, "
                                "or otherwise non-actionable."
                            ),
                        )
                    )

                allowed_quadrant = (
                    _trend_allowed_quadrant(
                        candidate
                    )
                )

                if quadrant != allowed_quadrant:
                    item_violations.append(
                        _violation(
                            code=(
                                "incompatible_trend_quadrant"
                            ),
                            quadrant=quadrant,
                            title=title or None,
                            source_theme=source_theme,
                            message=(
                                "The trend candidate does not "
                                "support the requested SWOT "
                                "quadrant."
                            ),
                        )
                    )

                authoritative_references = (
                    _candidate_references(
                        candidate
                    )
                )

                authoritative_frequency = 0

                confidence_ceiling = (
                    _candidate_confidence(
                        candidate
                    )
                )

                claim_strength = (
                    _candidate_claim_strength(
                        candidate
                    )
                )

                requires_manual_review = (
                    _candidate_requires_review(
                        candidate
                    )
                )

            elif source_theme:
                item_violations.append(
                    _violation(
                        code="unknown_source_theme",
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=source_theme,
                        message=(
                            "The source_theme is not an "
                            "available customer theme or "
                            "trend candidate."
                        ),
                    )
                )

            if authoritative_references:
                source_reference_set = set(
                    authoritative_references
                )

                mismatched_references = tuple(
                    reference
                    for reference in references
                    if (
                        reference
                        not in source_reference_set
                    )
                )

                if mismatched_references:
                    item_violations.append(
                        _violation(
                            code=(
                                "evidence_source_mismatch"
                            ),
                            quadrant=quadrant,
                            title=title or None,
                            source_theme=(
                                source_theme
                                or None
                            ),
                            invalid_references=(
                                mismatched_references
                            ),
                            message=(
                                "The evidence reference is "
                                "globally valid but does not "
                                "belong to this source_theme."
                            ),
                        )
                    )

            elif references and (
                theme is not None
                or candidate is not None
            ):
                item_violations.append(
                    _violation(
                        code="source_has_no_evidence",
                        quadrant=quadrant,
                        title=title or None,
                        source_theme=(
                            source_theme
                            or None
                        ),
                        invalid_references=references,
                        message=(
                            "The selected source_theme has "
                            "no authoritative evidence IDs."
                        ),
                    )
                )

            violations.extend(
                item_violations
            )

            error_codes = tuple(
                violation.code
                for violation
                in item_violations
                if (
                    violation.severity
                    == "error"
                )
            )

            if error_codes:
                blocked.append(
                    BlockedGroundedSwotItem(
                        quadrant=quadrant,
                        title=title,
                        source_theme=source_theme,
                        evidence_references=(
                            references
                        ),
                        violation_codes=(
                            error_codes
                        ),
                    )
                )

                continue

            score = _scoring(
                item
            )

            requested_confidence = (
                _bounded_float(
                    score.get(
                        "confidence",
                        confidence_ceiling,
                    ),
                    minimum=0.0,
                    maximum=1.0,
                    default=(
                        confidence_ceiling
                    ),
                )
            )

            safe_confidence = min(
                requested_confidence,
                confidence_ceiling,
            )

            safe_frequency = (
                authoritative_frequency
            )

            tags = _unique_strings(
                _as_list(
                    item.get(
                        "tags"
                    )
                )
            )[:5]

            accepted.append(
                SafeGroundedSwotItem(
                    quadrant=quadrant,
                    title=title,
                    reasoning=reasoning,
                    source_theme=source_theme,
                    tags=tags,
                    importance=(
                        _bounded_float(
                            score.get(
                                "importance",
                                5.0,
                            ),
                            minimum=0.0,
                            maximum=10.0,
                            default=5.0,
                        )
                    ),
                    impact=(
                        _bounded_float(
                            score.get(
                                "impact",
                                5.0,
                            ),
                            minimum=0.0,
                            maximum=10.0,
                            default=5.0,
                        )
                    ),
                    confidence=(
                        safe_confidence
                    ),
                    frequency=(
                        safe_frequency
                    ),
                    evidence_references=(
                        references
                    ),
                    origin=origin,
                    claim_strength=(
                        claim_strength
                    ),
                    requires_manual_review=(
                        requires_manual_review
                    ),
                    should_feed_strategy_agent=False,
                )
            )

    return GroundedSwotValidationResult(
        business_id=(
            bundle.business_id
        ),
        valid=not violations,
        accepted_items=tuple(
            accepted
        ),
        blocked_items=tuple(
            blocked
        ),
        violations=tuple(
            violations
        ),
        allowed_evidence_references=(
            bundle
            .allowed_evidence_references
        ),
        observed_evidence_references=tuple(
            observed_references
        ),
        requires_human_review=bool(
            accepted
            or blocked
            or violations
        ),
    )
