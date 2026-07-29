"""
SWOT Business Profile Builder

Converts Theme Extractor output into the exact BusinessProfile
contract consumed by SWOT Agent v7.

The builder preserves:

- Theme frequency.
- Sentiment distribution.
- Evidence references.
- Positive and negative signals.
- Opportunity and threat signals.
- Comparison summary.
- Review-count metadata.

The builder does not call an LLM and does not write to a database.
"""

from collections.abc import Mapping
from typing import Any

from app.agents.swot.schemas.input import (
    BusinessProfile,
    ReviewTheme,
    ReviewsSummary,
    SentimentBalance,
)


_SENTIMENT_KEYS = (
    "positive",
    "negative",
    "neutral",
    "mixed",
)


_KNOWN_SOURCE_PREFIXES = (
    "google_maps",
    "facebook",
    "instagram",
)

def _as_mapping(
    value: Any,
) -> dict[str, Any]:
    """Return a plain mapping for supported values."""

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


def _as_list(
    value: Any,
) -> list[Any]:
    """Return list values without inventing entries."""

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
    """Normalize required text with a safe fallback."""

    if isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        if cleaned:
            return cleaned

    return default


def _non_negative_int(
    value: Any,
    *,
    default: int = 0,
) -> int:
    """Normalize one non-negative integer."""

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


def _unique_references(
    values: list[Any],
) -> list[Any]:
    """Deduplicate evidence references while preserving order."""

    result: list[Any] = []

    seen_strings: set[str] = set()

    for value in values:
        if isinstance(
            value,
            str,
        ):
            cleaned = value.strip()

            if (
                not cleaned
                or cleaned in seen_strings
            ):
                continue

            seen_strings.add(
                cleaned
            )

            result.append(
                cleaned
            )

            continue

        if value not in result:
            result.append(
                value
            )

    return result
def _safe_optional_float(
    value: Any,
) -> float | None:
    """Return one finite float or None."""

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        normalized = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    return normalized


def _bounded_confidence(
    value: Any,
) -> float | None:
    """Normalize an optional confidence value to zero through one."""

    normalized = _safe_optional_float(
        value
    )

    if normalized is None:
        return None

    return max(
        0.0,
        min(
            1.0,
            normalized,
        ),
    )


def _representative_quotes(
    theme: dict[str, Any],
) -> list[str]:
    """Normalize representative quotes while preserving order."""

    raw_quotes = _as_list(
        theme.get(
            "representative_quotes",
            theme.get(
                "quotes",
                [],
            ),
        )
    )

    result: list[str] = []

    for raw_quote in raw_quotes:
        quote: str | None = None

        if isinstance(
            raw_quote,
            str,
        ):
            quote = raw_quote.strip()

        elif isinstance(
            raw_quote,
            Mapping,
        ):
            raw_text = raw_quote.get(
                "text"
            )

            if isinstance(
                raw_text,
                str,
            ):
                quote = raw_text.strip()

        if (
            quote
            and quote not in result
        ):
            result.append(
                quote
            )

    return result


def _source_from_reference(
    reference: Any,
) -> str | None:
    """Extract one known source platform from an evidence reference."""

    if not isinstance(
        reference,
        str,
    ):
        return None

    cleaned = reference.strip().lower()

    if not cleaned:
        return None

    prefix = cleaned.split(
        ":",
        maxsplit=1,
    )[0]

    if prefix in _KNOWN_SOURCE_PREFIXES:
        return prefix

    return None


def _theme_source_platforms(
    *,
    theme: dict[str, Any],
    evidence_references: list[Any],
) -> list[str]:
    """
    Preserve explicit source platforms or derive them from evidence.

    Source-aware references use forms such as:
    google_maps:review:<id>
    facebook:comment:<tagram:comment:<id>
    """

    explicit_sources = _as_list(
        theme.get(
            "source_platforms"
        )
    )

    result: list[str] = []

    for raw_source in explicit_sources:
        if not isinstance(
            raw_source,
            str,
        ):
            continue

        source = raw_source.strip().lower()

        if (
            source in _KNOWN_SOURCE_PREFIXES
            and source not in result
        ):
            result.append(
                source
            )

    for reference in evidence_references:
        source = _source_from_reference(
            reference
        )

        if (
            source is not None
            and source not in result
        ):
            result.append(
                source
            )

    return result

def _sentiment_distribution(
    theme: dict[str, Any],
) -> dict[str, int]:
    """
    Read Theme Extractor and legacy sentiment field names.

    Theme Extractor emits sentiment_distribution.
    Older callers may provide sentiment_balance.
    """

    raw_distribution = _as_mapping(
        theme.get(
            "sentiment_distribution",
            theme.get(
                "sentiment_balance",
                {},
            ),
        )
    )

    return {
        key: _non_negative_int(
            raw_distribution.get(
                key,
                0,
            )
        )
        for key in _SENTIMENT_KEYS
    }


def _theme_frequency(
    theme: dict[str, Any],
    mentions: list[Any],
) -> int:
    """
    Read Theme Extractor and legacy frequency field names.

    When neither value is available, the explicit mention count is
    used as a deterministic fallback.
    """

    if "frequency_count" in theme:
        return _non_negative_int(
            theme.get(
                "frequency_count"
            )
        )

    if "frequency" in theme:
        return _non_negative_int(
            theme.get(
                "frequency"
            )
        )

    return len(
        mentions
    )


def _theme_evidence_references(
    theme: dict[str, Any],
    mentions: list[Any],
) -> list[Any]:
    """
    Prefer explicit evidence references and fall back to mentions.

    Theme Extractor currently stores review IDs in mentions.
    """

    explicit_references = _as_list(
        theme.get(
            "evidence_refs"
        )
    )

    if explicit_references:
        return _unique_references(
            explicit_references
        )

    return _unique_references(
        mentions
    )


def _build_review_theme(
    raw_theme: Any,
) -> ReviewTheme | None:
    """Build one complete evidence-backed SWOT v7 ReviewTheme."""

    theme = _as_mapping(
        raw_theme
    )

    if not theme:
        return None

    theme_category = _clean_text(
        theme.get(
            "theme_category"
        ),
        default="",
    )

    if not theme_category:
        return None

    mentions = _as_list(
        theme.get(
            "mentions"
        )
    )

    distribution = (
        _sentiment_distribution(
            theme
        )
    )

    evidence_references = (
        _theme_evidence_references(
            theme,
            mentions,
        )
    )

    source_platforms = (
        _theme_source_platforms(
            theme=theme,
            evidence_references=(
                evidence_references
            ),
        )
    )

    return ReviewTheme(
        theme_category=theme_category,
        entity_type=_clean_text(
            theme.get(
                "entity_type"
            ),
            default="target_business",
        ),
        frequency=_theme_frequency(
            theme,
            mentions,
        ),
        sentiment_balance=(
            SentimentBalance(
                positive=distribution[
                    "positive"
                ],
                negative=distribution[
                    "negative"
                ],
                neutral=distribution[
                    "neutral"
                ],
                mixed=distribution[
                    "mixed"
                ],
            )
        ),
        confidence_score=(
            _bounded_confidence(
                theme.get(
                    "confidence_score"
                )
            )
        ),
        
        requires_manual_review=bool(
            theme.get(
                "requires_manual_review",
                False,
            )
        ),
        target_score=(
            _safe_optional_float(
                theme.get(
                    "target_score",
                    theme.get(
                        "_target_score"
                    ),
                )
            )
        ),
        competitor_score=(
            _safe_optional_float(
                theme.get(
                    "competitor_score",
                    theme.get(
                        "_competitor_score"
                    ),
                )
            )
        ),
        performance_gap=(
            _safe_optional_float(
                theme.get(
                    "performance_gap",
                    theme.get(
                        "_gap"
                    ),
                )
            )
        ),
        mentions=mentions,
        evidence_refs=(
            evidence_references
        ),
        representative_quotes=(
            _representative_quotes(
                theme
            )
        ),
        source_platforms=(
            source_platforms
        ),
    )


def build_swot_business_profile(
    *,
    business_name: str,
    business_type: str | None,
    themes_output: Mapping[str, Any],
    target_review_count: int | None = None,
    competitor_review_counts: (
        Mapping[str, int]
        | None
    ) = None,
) -> BusinessProfile:
    """
    Build the complete input consumed by SWOT Agent v7.

    The function supports the current Theme Extractor field names
    and the legacy aliases used by older test fixtures.
    """

    raw_themes = _as_list(
        themes_output.get(
            "themes"
        )
    )

    themes: list[ReviewTheme] = []

    for raw_theme in raw_themes:
        theme = _build_review_theme(
            raw_theme
        )

        if theme is not None:
            themes.append(
                theme
            )

    normalized_competitor_counts = {
        str(name): _non_negative_int(
            count
        )
        for name, count
        in (
            competitor_review_counts
            or {}
        ).items()
        if str(name).strip()
    }

    if target_review_count is not None:
        normalized_target_count = (
            _non_negative_int(
                target_review_count
            )
        )
    else:
        unique_target_references: list[Any] = []

        for theme in themes:
            if (
                theme.entity_type
                != "target_business"
            ):
                continue

            for reference in theme.evidence_refs:
                if (
                    reference
                    not in unique_target_references
                ):
                    unique_target_references.append(
                        reference
                    )

        normalized_target_count = len(
            unique_target_references
        )
    return BusinessProfile(
        business_name=_clean_text(
            business_name,
            default="Unknown",
        ),
        business_type=_clean_text(
            business_type,
            default="unknown",
        ),
        themes=themes,
        positive_signals=_as_list(
            themes_output.get(
                "positive_signals"
            )
        ),
        negative_signals=_as_list(
            themes_output.get(
                "negative_signals"
            )
        ),
        opportunity_signals=_as_list(
            themes_output.get(
                "opportunity_signals"
            )
        ),
        threat_signals=_as_list(
            themes_output.get(
                "threat_signals"
            )
        ),
        comparison_summary=_as_mapping(
            themes_output.get(
                "comparison_summary"
            )
        ),
        reviews_summary=ReviewsSummary(
            target_review_count=(
                normalized_target_count
            ),
            competitor_review_counts=(
                normalized_competitor_counts
            ),
        ),
    )


