"""Manual Starbucks semantic-theme test.

This test:
1. Loads the original Starbucks pipeline data.
2. Converts reviews.raw_samples into business_reviews.
3. Removes exact duplicate customer records.
4. Runs normalization.
5. Runs Gemini semantic theme extraction.
6. Validates that generic themes such as Good and Omg
   are not returned.

Docker and databases are not required.

Vertex AI credentials are required.

Run manually:

    python test_quick.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.preprocessing.normalize import (
    normalize_raw_data,
)
from app.preprocessing.theme_extractor import (
    extract_themes_from_normalized,
)


DATA_FILE = Path(
    __file__
).with_name(
    "starbucks_test_data.json"
)


def load_original_data() -> dict[str, Any]:
    """Load the original Starbucks pipeline data."""

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Test data file was not found: {DATA_FILE}"
        )

    return json.loads(
        DATA_FILE.read_text(
            encoding="utf-8",
        )
    )


def deduplicate_reviews(
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact duplicate customer records.

    The deduplication key uses:
    - cleaned text
    - source
    - date

    The original review text is preserved.
    """

    unique_reviews: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str, str]
    ] = set()

    for review in reviews:
        text = str(
            review.get(
                "text",
                "",
            )
        ).strip()

        source = str(
            review.get(
                "source",
                "unknown",
            )
        ).strip().lower()

        date = str(
            review.get(
                "date",
                "",
            )
        ).strip()

        if not text:
            continue

        duplicate_key = (
            text.casefold(),
            source,
            date,
        )

        if duplicate_key in seen:
            continue

        seen.add(
            duplicate_key
        )

        unique_reviews.append(
            {
                "text": text,
                "rating": review.get(
                    "rating"
                ),
                "source": source,
                "date": date,
            }
        )

    return unique_reviews


def build_normalizer_input(
    original_data: dict[str, Any],
) -> dict[str, Any]:
    """Map original pipeline output to normalizer input.

    No customer comments are invented or rewritten.
    """

    business_identity = dict(
        original_data.get(
            "business_identity",
            {},
        )
    )

    if (
        business_identity.get(
            "business_name"
        )
        and not business_identity.get(
            "name"
        )
    ):
        business_identity["name"] = (
            business_identity[
                "business_name"
            ]
        )

    reviews_envelope = (
        original_data.get(
            "reviews",
            {},
        )
    )

    raw_samples = (
        reviews_envelope.get(
            "raw_samples",
            [],
        )
    )

    if not isinstance(
        raw_samples,
        list,
    ):
        raise TypeError(
            "reviews.raw_samples must be a list."
        )

    unique_reviews = (
        deduplicate_reviews(
            raw_samples
        )
    )

    return {
        "business_identity": (
            business_identity
        ),
        "offerings": original_data.get(
            "offerings",
            [],
        ),
        "marketing_signals": (
            original_data.get(
                "marketing_signals",
                {},
            )
        ),
        "brand_voice": original_data.get(
            "brand_voice",
            {},
        ),
        "visual_identity": (
            original_data.get(
                "visual_identity",
                {},
            )
        ),
        "business_reviews": (
            unique_reviews
        ),
        "competitors": original_data.get(
            "competitors",
            [],
        ),
        "evidence_refs": (
            original_data.get(
                "evidence_refs",
                [],
            )
        ),
        "quality_report": {
            "source": (
                "starbucks_test_data"
            ),
            "original_review_count": len(
                raw_samples
            ),
            "unique_review_count": len(
                unique_reviews
            ),
        },
    }


def print_signal_section(
    title: str,
    signals: list[dict[str, Any]],
) -> None:
    """Print one signal group."""

    print(
        f"\n{title}: {len(signals)}"
    )

    for index, signal in enumerate(
        signals,
        start=1,
    ):
        print(
            f"  {index}. "
            f"{signal.get('theme_name')}"
        )

        print(
            "     Category: "
            f"{signal.get('theme_category')}"
        )

        print(
            "     Reason: "
            f"{signal.get('reason')}"
        )

        print(
            "     Mentions: "
            f"{signal.get('frequency_count')}"
        )

        print(
            "     Manual review: "
            f"{signal.get('requires_manual_review', False)}"
        )


def main() -> None:
    """Run the manual Starbucks semantic-theme test."""

    print("=" * 70)
    print(
        "STARBUCKS SEMANTIC THEME EXTRACTION TEST"
    )
    print("=" * 70)

    original_data = (
        load_original_data()
    )

    raw_samples = (
        original_data.get(
            "reviews",
            {},
        ).get(
            "raw_samples",
            [],
        )
    )

    print(
        "\nOriginal raw samples: "
        f"{len(raw_samples)}"
    )

    normalizer_input = (
        build_normalizer_input(
            original_data
        )
    )

    unique_input_reviews = (
        normalizer_input[
            "business_reviews"
        ]
    )

    print(
        "Unique records after deduplication: "
        f"{len(unique_input_reviews)}"
    )

    if not unique_input_reviews:
        raise RuntimeError(
            "No customer records remained "
            "after deduplication."
        )

    print(
        "\n[1/2] Running normalization..."
    )

    normalized = normalize_raw_data(
        normalizer_input
    )

    normalized_reviews = (
        normalized.get(
            "business_reviews",
            [],
        )
    )

    normalized_competitors = (
        normalized.get(
            "competitors",
            [],
        )
    )

    print(
        "  Normalized business reviews: "
        f"{len(normalized_reviews)}"
    )

    print(
        "  Competitors: "
        f"{len(normalized_competitors)}"
    )

    if not normalized_reviews:
        raise RuntimeError(
            "Normalization produced no "
            "business reviews."
        )

    print(
        "\n[2/2] Running Gemini "
        "semantic theme extraction..."
    )

    result = (
        extract_themes_from_normalized(
            normalized
        )
    )

    themes = result.get(
        "themes",
        [],
    )

    positive_signals = result.get(
        "positive_signals",
        [],
    )

    negative_signals = result.get(
        "negative_signals",
        [],
    )

    opportunity_signals = result.get(
        "opportunity_signals",
        [],
    )

    threat_signals = result.get(
        "threat_signals",
        [],
    )

    if not themes:
        raise RuntimeError(
            "Gemini produced no validated "
            "semantic themes."
        )

    print(
        f"\nThemes found: {len(themes)}"
    )

    print("\nExtracted themes:")

    for index, theme in enumerate(
        themes,
        start=1,
    ):
        print(
            f"\n  {index}. "
            f"{theme.get('theme_name')}"
        )

        print(
            "     Category: "
            f"{theme.get('theme_category')}"
        )

        print(
            "     Entity: "
            f"{theme.get('entity_type')}"
        )

        print(
            "     Mentions: "
            f"{theme.get('frequency_count')}"
        )

        print(
            "     Confidence: "
            f"{theme.get('confidence_score')}"
        )

        print(
            "     Manual review: "
            f"{theme.get('requires_manual_review', False)}"
        )

        summary = theme.get(
            "summary"
        )

        if summary:
            print(
                f"     Summary: {summary}"
            )

        quotes = theme.get(
            "representative_quotes",
            [],
        )

        if quotes:
            print(
                "     Evidence sample:"
            )

            for quote in quotes[:2]:
                print(
                    f"       - {quote}"
                )

    generic_names = {
        "good",
        "omg",
        "wow",
        "nice",
        "amazing",
        "emerging theme: good",
        "emerging theme: omg",
    }

    returned_names = {
        str(
            theme.get(
                "theme_name",
                "",
            )
        ).strip().lower()
        for theme in themes
    }

    invalid_names = (
        returned_names
        & generic_names
    )

    if invalid_names:
        raise RuntimeError(
            "Generic theme names were returned: "
            f"{sorted(invalid_names)}"
        )

    all_mentions = {
        mention_id
        for theme in themes
        for mention_id in theme.get(
            "mentions",
            [],
        )
    }

    valid_review_ids = {
        str(
            review.get(
                "review_id",
                "",
            )
        )
        for review in normalized_reviews
        if review.get(
            "review_id"
        )
    }

    invented_mentions = (
        all_mentions
        - valid_review_ids
    )

    if invented_mentions:
        raise RuntimeError(
            "Unknown evidence IDs were returned: "
            f"{sorted(invented_mentions)}"
        )

    print_signal_section(
        "Positive signals",
        positive_signals,
    )

    print_signal_section(
        "Negative signals",
        negative_signals,
    )

    print_signal_section(
        "Opportunity signals",
        opportunity_signals,
    )

    print_signal_section(
        "Threat signals",
        threat_signals,
    )

    print("\n" + "=" * 70)
    print("SUCCESS")
    print(
        "The original Starbucks data produced "
        "validated semantic business themes."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
