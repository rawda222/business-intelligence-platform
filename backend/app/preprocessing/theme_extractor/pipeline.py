"""
Theme Extractor - Semantic AI Pipeline
======================================

Pipeline:
1. Collect normalized customer records
2. Extract semantic business themes using Gemini
3. Validate all evidence IDs in Python
4. Compute competitor comparisons
5. Derive business signals
6. Rank themes
7. Return the public response contract
"""

from typing import Any, Dict

from app.preprocessing.theme_extractor.reviews import (
    collect_all_reviews,
)
from app.preprocessing.theme_extractor.semantic import (
    extract_semantic_signals,
    extract_semantic_theme_records,
)
from app.preprocessing.theme_extractor.comparative import (
    build_comparison_summary,
    compute_comparative_signals,
)
from app.preprocessing.theme_extractor.ranking import (
    rank_themes,
    strip_internal_fields,
)


def extract_themes(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract validated semantic business themes.

    Raises a clear error if Gemini cannot produce
    usable business-relevant themes.
    """

    reviews = collect_all_reviews(
        data
    )

    if not reviews:
        raise ValueError(
            "No customer records were available "
            "for theme extraction."
        )

    theme_records = (
        extract_semantic_theme_records(
            data=data,
            reviews=reviews,
        )
    )

    comparative_records = (
        compute_comparative_signals(
            theme_records
        )
    )

    theme_records.extend(
        comparative_records
    )

    (
        positive,
        negative,
        opportunity,
        threat,
    ) = extract_semantic_signals(
        theme_records
    )

    comparison_summary = (
        build_comparison_summary(
            comparative_records
        )
    )

    ranked = rank_themes(
        theme_records
    )

    cleaned_themes = [
        strip_internal_fields(record)
        for record in ranked
    ]

    if not cleaned_themes:
        raise ValueError(
            "No validated semantic themes "
            "were produced."
        )

    return {
        "themes": cleaned_themes,
        "positive_signals": (
            positive
        ),
        "negative_signals": (
            negative
        ),
        "opportunity_signals": (
            opportunity
        ),
        "threat_signals": (
            threat
        ),
        "comparison_summary": (
            comparison_summary
        ),
    }


def extract_themes_from_normalized(
    normalized_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Public entry point used by FastAPI services.
    """

    return extract_themes(
        normalized_data
    )