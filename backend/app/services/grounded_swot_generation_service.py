"""
Grounded SWOT Generation Service

Runs SWOT Agent v7 against an evidence-controlled Strong SWOT
input bundle, then validates and safely reconstructs the generated
SWOT items.

The LLM output is always treated as untrusted input.

The service:

- Supports Vertex Gemini through SWOT Agent v7.
- Supports dependency injection for deterministic tests.
- Validates all generated items against the evidence bundle.
- Preserves provider and fallback metadata.
- Never enables Strategy routing before human approval.
- Does not persist reports to MongoDB.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.agents.swot import (
    LLMProvider,
    SWOTAgent,
)
from app.services.grounded_swot_output_validator import (
    GroundedSwotValidationResult,
    SafeGroundedSwotItem,
    validate_grounded_swot_output,
)
from app.services.strong_swot_input_service import (
    StrongSwotInputBundle,
)


@dataclass(frozen=True, slots=True)
class GroundedSwotGenerationResult:
    """Complete result of grounded SWOT generation."""

    business_id: Any

    generated_output: Any

    validation: GroundedSwotValidationResult

    provider_used: str

    model_used: str

    fallback_used: bool

    raw_item_count: int

    accepted_item_count: int

    blocked_item_count: int

    safe_for_update_proposal: bool

    requires_human_review: bool

    source_coverage: tuple[str, ...]

    allowed_evidence_references: tuple[str, ...]

    warnings: tuple[str, ...]

    @property
    def accepted_items(
        self,
    ) -> tuple[SafeGroundedSwotItem, ...]:
        """Return validated items accepted by Python."""

        return self.validation.accepted_items


def _as_mapping(
    value: Any,
) -> dict[str, Any]:
    """Convert mapping-like and Pydantic-like values to a dict."""

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
    *,
    default: str,
) -> str:
    """Return normalized text with a deterministic fallback."""

    if isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        if cleaned:
            return cleaned

    return default


def _unique_strings(
    values: list[Any],
) -> tuple[str, ...]:
    """Normalize and deduplicate strings in source order."""

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


def _extract_report(
    generated_output: Any,
) -> dict[str, Any]:
    """Extract the generated SWOT report from supported shapes."""

    output = _as_mapping(
        generated_output
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

    return output


def _raw_item_count(
    generated_output: Any,
) -> int:
    """Count all generated items before grounded validation."""

    report = _extract_report(
        generated_output
    )

    return sum(
        len(
            _as_list(
                report.get(
                    quadrant,
                    [],
                )
            )
        )
        for quadrant in (
            "strengths",
            "weaknesses",
            "opportunities",
            "threats",
        )
    )


def _generation_metadata(
    generated_output: Any,
) -> tuple[str, str, bool]:
    """Read provider, model, and fallback metadata safely."""

    output = _as_mapping(
        generated_output
    )

    meta = _as_mapping(
        output.get(
            "meta"
        )
    )

    provider_used = _clean_text(
        meta.get(
            "llm_provider_used"
        ),
        default="unknown",
    )

    model_used = _clean_text(
        meta.get(
            "llm_model_used"
        ),
        default="unknown",
    )

    fallback_used = bool(
        meta.get(
            "fallback_used",
            False,
        )
    )

    return (
        provider_used,
        model_used,
        fallback_used,
    )


def _build_generation_warnings(
    *,
    bundle: StrongSwotInputBundle,
    validation: GroundedSwotValidationResult,
    fallback_used: bool,
) -> tuple[str, ...]:
    """Build ordered warnings from generation and validation."""

    warnings: list[str] = list(
        bundle.warnings
    )

    if fallback_used:
        warnings.append(
            "generation:"
            "rule_based_fallback_used"
        )

    if not validation.accepted_items:
        warnings.append(
            "generation:"
            "no_grounded_items_accepted"
        )

    if validation.blocked_items:
        warnings.append(
            "generation:"
            "one_or_more_items_blocked"
        )

    if any(
        violation.severity == "error"
        for violation in validation.violations
    ):
        warnings.append(
            "generation:"
            "evidence_validation_failed"
        )

    return _unique_strings(
        warnings
    )


def _build_default_agent(
    *,
    provider: LLMProvider,
    model: str | None,
    dry_run: bool,
) -> SWOTAgent:
    """Build the production SWOT Agent v7."""

    return SWOTAgent(
        provider=provider,
        model=model,
        dry_run=dry_run,
    )


def generate_grounded_swot(
    *,
    bundle: StrongSwotInputBundle,
    agent: Any | None = None,
    provider: LLMProvider = LLMProvider.VERTEX_AI,
    model: str | None = "gemini-2.5-flash",
    dry_run: bool = False,
) -> GroundedSwotGenerationResult:
    """
    Generate and validate one evidence-grounded SWOT.

    When agent is omitted, SWOT Agent v7 is created with the
    requested provider and model.

    A supplied agent must expose:

        run(profile) -> generated SWOT output
    """

    effective_agent = (
        agent
        if agent is not None
        else _build_default_agent(
            provider=provider,
            model=model,
            dry_run=dry_run,
        )
    )

    run_method = getattr(
        effective_agent,
        "run",
        None,
    )

    if not callable(
        run_method
    ):
        raise TypeError(
            "The SWOT generation agent must expose "
            "a callable run(profile) method."
        )

    generated_output = run_method(
        bundle.swot_profile
    )

    validation = (
        validate_grounded_swot_output(
            bundle=bundle,
            llm_output=generated_output,
        )
    )

    (
        provider_used,
        model_used,
        fallback_used,
    ) = _generation_metadata(
        generated_output
    )

    raw_item_count = _raw_item_count(
        generated_output
    )

    accepted_item_count = len(
        validation.accepted_items
    )

    blocked_item_count = len(
        validation.blocked_items
    )

    has_error_violations = any(
        violation.severity == "error"
        for violation in validation.violations
    )

    strategy_routing_is_safe = all(
        not item.should_feed_strategy_agent
        for item in validation.accepted_items
    )

    safe_for_update_proposal = (
        accepted_item_count > 0
        and blocked_item_count == 0
        and not has_error_violations
        and strategy_routing_is_safe
    )

    warnings = _build_generation_warnings(
        bundle=bundle,
        validation=validation,
        fallback_used=fallback_used,
    )

    return GroundedSwotGenerationResult(
        business_id=bundle.business_id,
        generated_output=generated_output,
        validation=validation,
        provider_used=provider_used,
        model_used=model_used,
        fallback_used=fallback_used,
        raw_item_count=raw_item_count,
        accepted_item_count=(
            accepted_item_count
        ),
        blocked_item_count=(
            blocked_item_count
        ),
        safe_for_update_proposal=(
            safe_for_update_proposal
        ),
        requires_human_review=(
            validation.requires_human_review
        ),
        source_coverage=(
            bundle.source_coverage
        ),
        allowed_evidence_references=(
            bundle
            .allowed_evidence_references
        ),
        warnings=warnings,
    )
