"""
Legacy SWOT Adapter

Normalizes stored SWOT reports into one conservative contract that
supports both:

- The current lightweight SWOT Agent v1 output.
- The richer production-grade SWOT v7 output.

Missing safety fields are never treated as approval. A legacy item
without explicit claim-strength and routing metadata requires manual
review and cannot automatically feed the Strategy Agent.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID


NormalizedSwotQuadrant = Literal[
    "strength",
    "weakness",
    "opportunity",
    "threat",
]

NormalizedClaimStrength = Literal[
    "validated",
    "internally_supported",
    "directional_not_validated",
    "early_warning",
]


QUADRANT_KEYS: tuple[
    tuple[str, NormalizedSwotQuadrant],
    ...
] = (
    (
        "strengths",
        "strength",
    ),
    (
        "weaknesses",
        "weakness",
    ),
    (
        "opportunities",
        "opportunity",
    ),
    (
        "threats",
        "threat",
    ),
)

KNOWN_CLAIM_STRENGTHS = {
    "validated",
    "internally_supported",
    "directional_not_validated",
    "early_warning",
}

DEFAULT_BASELINE_SOURCES = (
    "business_profile",
    "google_maps_reviews",
)


@dataclass(frozen=True, slots=True)
class NormalizedSwotItem:
    """One normalized item from an existing SWOT report."""

    item_id: str

    item_id_was_generated: bool

    quadrant: NormalizedSwotQuadrant

    title: str

    reasoning: str

    source_theme: str | None

    confidence: float

    strategic_priority: float

    claim_strength: NormalizedClaimStrength

    source_should_feed_strategy_agent: bool

    should_feed_strategy_agent: bool

    manual_review_only: bool

    evidence_references: tuple[
        str,
        ...
    ]

    normalization_warnings: tuple[
        str,
        ...
    ]


@dataclass(frozen=True, slots=True)
class NormalizedSwotBaseline:
    """Normalized baseline used by the SWOT update-proposal layer."""

    business_id: UUID

    report_id: UUID

    engine_version: str

    source_coverage: tuple[
        str,
        ...
    ]

    items: tuple[
        NormalizedSwotItem,
        ...
    ]

    warnings: tuple[
        str,
        ...
    ]


def _as_mapping(
    value: Any,
) -> dict[str, Any]:
    """Convert supported objects into a plain mapping."""

    if isinstance(
        value,
        Mapping,
    ):
        return dict(
            value
        )

    if hasattr(
        value,
        "model_dump",
    ):
        dumped = value.model_dump()

        if isinstance(
            dumped,
            Mapping,
        ):
            return dict(
                dumped
            )

    return {}


def _clean_text(
    value: Any,
) -> str:
    """Return one stripped string or an empty string."""

    if not isinstance(
        value,
        str,
    ):
        return ""

    return value.strip()


def _safe_float(
    value: Any,
    *,
    default: float = 0.0,
) -> float:
    """Convert a value to float without leaking invalid numbers."""

    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    return result


def _clamp_confidence(
    value: Any,
) -> float:
    """Normalize confidence to the zero-to-one range."""

    return max(
        0.0,
        min(
            1.0,
            _safe_float(
                value,
            ),
        ),
    )


def _normalize_claim_strength(
    value: Any,
) -> tuple[
    NormalizedClaimStrength,
    bool,
]:
    """
    Normalize claim strength.

    The boolean indicates whether the value was explicitly valid.
    """

    cleaned = _clean_text(
        value
    ).lower()

    if cleaned in KNOWN_CLAIM_STRENGTHS:
        return (
            cleaned,
            True,
        )

    return (
        "directional_not_validated",
        False,
    )


def _extract_evidence_reference(
    value: Any,
) -> str | None:
    """Extract an explicit reference without inventing one."""

    if isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        return cleaned or None

    data = _as_mapping(
        value
    )

    for field_name in (
        "reference",
        "id",
        "review_id",
        "source_id",
        "evidence_id",
    ):
        cleaned = _clean_text(
            data.get(
                field_name
            )
        )

        if cleaned:
            return cleaned

    return None


def _normalize_evidence_references(
    item: dict[str, Any],
) -> tuple[
    str,
    ...
]:
    """Normalize evidence references while preserving order."""

    raw_references = item.get(
        "evidence_refs",
        item.get(
            "evidence_references",
            [],
        ),
    )

    if not isinstance(
        raw_references,
        (
            list,
            tuple,
        ),
    ):
        return ()

    result: list[str] = []

    for raw_reference in raw_references:
        reference = (
            _extract_evidence_reference(
                raw_reference
            )
        )

        if (
            reference is not None
            and reference not in result
        ):
            result.append(
                reference
            )

    return tuple(
        result
    )


def _normalize_item(
    *,
    raw_item: Any,
    quadrant: NormalizedSwotQuadrant,
    item_index: int,
) -> NormalizedSwotItem | None:
    """Normalize one existing SWOT item conservatively."""

    item = _as_mapping(
        raw_item
    )

    if not item:
        return None

    title = _clean_text(
        item.get(
            "title"
        )
    )

    if not title:
        return None

    warnings: list[str] = []

    item_id = _clean_text(
        item.get(
            "item_id"
        )
    )

    item_id_was_generated = (
        not item_id
    )

    if item_id_was_generated:
        item_id = (
            "legacy:"
            f"{quadrant}:"
            f"{item_index}"
        )

        warnings.append(
            "The stored SWOT item had no item_id; "
            "a deterministic adapter ID was generated."
        )

    scoring = _as_mapping(
        item.get(
            "scoring"
        )
    )

    confidence = _clamp_confidence(
        scoring.get(
            "confidence",
            item.get(
                "confidence",
                0.0,
            ),
        )
    )

    strategic_priority = max(
        0.0,
        _safe_float(
            scoring.get(
                "strategic_priority",
                item.get(
                    "strategic_priority",
                    0.0,
                ),
            )
        ),
    )

    (
        claim_strength,
        has_explicit_claim_strength,
    ) = _normalize_claim_strength(
        item.get(
            "claim_strength"
        )
    )

    if not has_explicit_claim_strength:
        warnings.append(
            "The stored SWOT item had no valid "
            "claim_strength and was normalized as "
            "directional_not_validated."
        )

    raw_strategy_flag = item.get(
        "should_feed_strategy_agent"
    )

    has_explicit_strategy_flag = isinstance(
        raw_strategy_flag,
        bool,
    )

    source_strategy_flag = (
        raw_strategy_flag
        if has_explicit_strategy_flag
        else False
    )

    if not has_explicit_strategy_flag:
        warnings.append(
            "The stored SWOT item had no explicit "
            "Strategy routing flag."
        )

    raw_manual_review = item.get(
        "manual_review_only"
    )

    has_explicit_manual_review = isinstance(
        raw_manual_review,
        bool,
    )

    manual_review_only = (
        raw_manual_review
        if has_explicit_manual_review
        else True
    )

    if not has_explicit_manual_review:
        warnings.append(
            "The stored SWOT item had no explicit "
            "manual-review flag and was conservatively "
            "marked for review."
        )

    evidence_references = (
        _normalize_evidence_references(
            item
        )
    )

    if not evidence_references:
        warnings.append(
            "The stored SWOT item has no normalized "
            "evidence references."
        )

    should_feed_strategy_agent = (
        source_strategy_flag
        and not manual_review_only
        and claim_strength
        in {
            "validated",
            "internally_supported",
        }
        and bool(
            evidence_references
        )
    )

    return NormalizedSwotItem(
        item_id=item_id,
        item_id_was_generated=(
            item_id_was_generated
        ),
        quadrant=quadrant,
        title=title,
        reasoning=_clean_text(
            item.get(
                "reasoning"
            )
        ),
        source_theme=(
            _clean_text(
                item.get(
                    "source_theme"
                )
            )
            or None
        ),
        confidence=confidence,
        strategic_priority=(
            strategic_priority
        ),
        claim_strength=claim_strength,
        source_should_feed_strategy_agent=(
            source_strategy_flag
        ),
        should_feed_strategy_agent=(
            should_feed_strategy_agent
        ),
        manual_review_only=(
            manual_review_only
        ),
        evidence_references=(
            evidence_references
        ),
        normalization_warnings=tuple(
            warnings
        ),
    )


def normalize_legacy_swot(
    *,
    business_id: UUID,
    report_id: UUID,
    engine_version: str,
    swot_report: Any,
    source_coverage: tuple[
        str,
        ...
    ] = DEFAULT_BASELINE_SOURCES,
) -> NormalizedSwotBaseline:
    """
    Normalize a stored SWOT report for evidence-based updating.

    The function never upgrades missing safety metadata into an
    approved or Strategy-eligible claim.
    """

    report_data = _as_mapping(
        swot_report
    )

    normalized_items: list[
        NormalizedSwotItem
    ] = []

    baseline_warnings: list[str] = []

    if not report_data:
        baseline_warnings.append(
            "The stored SWOT report is empty or invalid."
        )

    for (
        source_key,
        normalized_quadrant,
    ) in QUADRANT_KEYS:
        raw_items = report_data.get(
            source_key,
            [],
        )

        if not isinstance(
            raw_items,
            (
                list,
                tuple,
            ),
        ):
            baseline_warnings.append(
                f"The '{source_key}' SWOT collection "
                "was not a list and was ignored."
            )

            continue

        for item_index, raw_item in enumerate(
            raw_items,
            start=1,
        ):
            normalized_item = _normalize_item(
                raw_item=raw_item,
                quadrant=(
                    normalized_quadrant
                ),
                item_index=item_index,
            )

            if normalized_item is None:
                baseline_warnings.append(
                    f"An invalid '{source_key}' item "
                    f"at position {item_index} was ignored."
                )

                continue

            normalized_items.append(
                normalized_item
            )

    return NormalizedSwotBaseline(
        business_id=business_id,
        report_id=report_id,
        engine_version=(
            _clean_text(
                engine_version
            )
            or "unknown"
        ),
        source_coverage=tuple(
            dict.fromkeys(
                source_coverage
            )
        ),
        items=tuple(
            normalized_items
        ),
        warnings=tuple(
            baseline_warnings
        ),
    )
