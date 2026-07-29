"""
Scraper Adapter
===============

Converts scraper output into the standardized input expected by
the Business Intelligence preprocessing pipeline.

Supported inputs:

1. Scraper output:
   - business_identity
   - reviews.raw_samples
   - competitors

2. Pipeline-style input:
   - business_name
   - business_reviews
   - competitors

The adapter also removes exact duplicate customer records while
preserving the original text and relevant metadata.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List


def adapt_scraper_data(
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert raw scraper data into BI Pipeline input format.

    The returned structure contains:

    - business_name
    - business_type
    - business_profile
    - business_reviews
    - competitors
    - evidence_refs
    - quality_report
    - optional brand and marketing fields
    """

    if not isinstance(raw, dict):
        raise TypeError(
            "Scraper input must be a dictionary."
        )

    output: Dict[str, Any] = {}

    # ========================================================
    # Business Identity
    # ========================================================

    identity = raw.get(
        "business_identity",
        {},
    ) or {}

    if not isinstance(identity, dict):
        identity = {}

    business_name = (
        identity.get("business_name")
        or identity.get("name")
        or raw.get("business_name")
        or "Unknown"
    )

    category = (
        identity.get("subcategory")
        or identity.get("category")
        or raw.get("business_type")
        or "general"
    )

    output["business_name"] = str(
        business_name
    ).strip()

    output["business_type"] = (
        str(category)
        .strip()
        .lower()
        .replace(" ", "_")
    )

    output["business_profile"] = {
        "business_identity": identity,
        "offerings": raw.get(
            "offerings",
            [],
        ),
        "marketing_signals": raw.get(
            "marketing_signals",
            {},
        ),
        "brand_voice": raw.get(
            "brand_voice",
            {},
        ),
        "commercial": raw.get(
            "commercial",
            {},
        ),
        "contact_presence": raw.get(
            "contact_presence",
            {},
        ),
        "visual_identity": raw.get(
            "visual_identity",
            {},
        ),
        "insights": raw.get(
            "insights",
            {},
        ),
        "known_competitors": raw.get(
            "known_competitors",
            [],
        ),
        "confidence": raw.get(
            "confidence",
            {},
        ),
        "schema_version": raw.get(
            "schema_version",
        ),
    }

    # ========================================================
    # Business Reviews
    # ========================================================

    raw_samples = _find_business_reviews(
        raw
    )

    business_reviews: List[
        Dict[str, Any]
    ] = []

    for review in raw_samples:
        normalized_review = (
            _adapt_review_record(
                review
            )
        )

        if normalized_review is not None:
            business_reviews.append(
                normalized_review
            )

    output["business_reviews"] = (
        _deduplicate_reviews(
            business_reviews
        )
    )

    # ========================================================
    # Competitors
    # ========================================================

    adapted_competitors: List[
        Dict[str, Any]
    ] = []

    raw_competitors = raw.get(
        "competitors",
        [],
    ) or []

    if not isinstance(
        raw_competitors,
        list,
    ):
        raw_competitors = []

    for competitor in raw_competitors:
        if not isinstance(
            competitor,
            dict,
        ):
            continue

        competitor_reviews: List[
            Dict[str, Any]
        ] = []

        reviews_sample = (
            competitor.get(
                "reviews_sample",
                [],
            )
            or competitor.get(
                "reviews",
                [],
            )
            or []
        )

        if not isinstance(
            reviews_sample,
            list,
        ):
            reviews_sample = []

        for review in reviews_sample:
            normalized_review = (
                _adapt_review_record(
                    review
                )
            )

            if normalized_review is not None:
                competitor_reviews.append(
                    normalized_review
                )

        competitor_reviews = (
            _deduplicate_reviews(
                competitor_reviews
            )
        )

        adapted_competitors.append(
            {
                "name": (
                    competitor.get("name")
                    or "Competitor"
                ),
                "reviews": (
                    competitor_reviews
                ),
                "reviews_sample": (
                    competitor_reviews
                ),
                "rating": competitor.get(
                    "rating"
                ),
                "review_count": (
                    competitor.get(
                        "review_count"
                    )
                ),
                "website": competitor.get(
                    "website"
                ),
                "maps_url": competitor.get(
                    "maps_url"
                ),
                "positioning": (
                    competitor.get(
                        "positioning"
                    )
                ),
                "description": (
                    competitor.get(
                        "description"
                    )
                ),
                "discovery_method": (
                    competitor.get(
                        "discovery_method"
                    )
                ),
                "peer_fit_score": (
                    competitor.get(
                        "peer_fit_score"
                    )
                ),
                "website_facts": (
                    competitor.get(
                        "website_facts",
                        [],
                    )
                ),
            }
        )

    output["competitors"] = (
        adapted_competitors
    )

    # ========================================================
    # Evidence and Quality Metadata
    # ========================================================

    output["evidence_refs"] = raw.get(
        "evidence_refs",
        [],
    ) or []

    original_review_count = len(
        raw_samples
    )

    unique_review_count = len(
        output["business_reviews"]
    )

    existing_quality_report = raw.get(
        "quality_report",
        {},
    ) or {}

    if not isinstance(
        existing_quality_report,
        dict,
    ):
        existing_quality_report = {}

    output["quality_report"] = {
        **existing_quality_report,
        "adapter": "scraper_adapter",
        "original_review_count": (
            original_review_count
        ),
        "unique_review_count": (
            unique_review_count
        ),
        "duplicates_removed": max(
            0,
            original_review_count
            - unique_review_count,
        ),
    }

    # ========================================================
    # Optional Top-Level Fields
    # ========================================================

    optional_fields = (
        "offerings",
        "marketing_signals",
        "brand_voice",
        "commercial",
        "contact_presence",
        "visual_identity",
        "insights",
        "known_competitors",
        "confidence",
        "schema_version",
    )

    for field_name in optional_fields:
        if field_name in raw:
            output[field_name] = raw[
                field_name
            ]

    return output


def _find_business_reviews(
    raw: Dict[str, Any],
) -> List[Any]:
    """
    Find customer records across supported input paths.

    Search order:

    1. reviews.raw_samples
    2. raw_samples
    3. business_reviews
    """
    reviews_block = raw.get(
        "reviews",
        {},
    ) or {}

    if not isinstance(
        reviews_block,
        dict,
    ):
        reviews_block = {}

    raw_samples = reviews_block.get(
        "raw_samples",
        [],
    ) or []

    if not raw_samples:
        raw_samples = raw.get(
            "raw_samples",
            [],
        ) or []

    if not raw_samples:
        raw_samples = raw.get(
            "business_reviews",
            [],
        ) or []

    if not isinstance(
        raw_samples,
        list,
    ):
        raise TypeError(
            "Customer review records must be a list."
        )

    return raw_samples


def _adapt_review_record(
    review_item: Any,
) -> Dict[str, Any] | None:
    """
    Convert one Review or Comment into pipeline format.

    The original text is preserved after whitespace cleanup.
    """

    if isinstance(
        review_item,
        str,
    ):
        text = _clean_review_text(
            review_item
        )

        if not text:
            return None

        return {
            "text": text,
            "rating": None,
            "source": "unknown",
            "date": None,
        }

    if not isinstance(
        review_item,
        dict,
    ):
        return None

    text = _extract_text(
        review_item
    )

    if not text:
        return None

    adapted: Dict[str, Any] = {
        "text": text,
        "rating": review_item.get(
            "rating"
        ),
        "source": (
            review_item.get("source")
            or review_item.get("platform")
            or "unknown"
        ),
        "date": (
            review_item.get("date")
            or review_item.get(
                "published_at"
            )
            or review_item.get(
                "created_at"
            )
        ),
    }

    optional_fields = (
        "review_id",
        "record_id",
        "id",
        "author",
        "language",
        "sentiment",
        "category_tags",
        "likes",
        "comments",
        "shares",
        "engagement",
        "url",
    )

    for field_name in optional_fields:
        if field_name in review_item:
            adapted[field_name] = (
                review_item[field_name]
            )

    return adapted


def _deduplicate_reviews(
    reviews: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove exact duplicate customer records.

    Duplicate identity uses:

    - normalized text
    - normalized source
    - normalized date

    The first original record is preserved.
    """

    unique_reviews: List[
        Dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str, str]
    ] = set()

    for review in reviews:
        if not isinstance(
            review,
            dict,
        ):
            continue

        text = _clean_review_text(
            str(
                review.get(
                    "text",
                    "",
                )
            )
        )

        source = (
            str(
                review.get(
                    "source",
                    "unknown",
                )
            )
            .strip()
            .casefold()
        )

        date_value = review.get(
            "date"
        )

        date = (
            ""
            if date_value is None
            else str(date_value).strip()
        )

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

        preserved_record = dict(
            review
        )

        preserved_record["text"] = (
            text
        )

        preserved_record["source"] = (
            source
        )

        unique_reviews.append(
            preserved_record
        )

    return unique_reviews


def _extract_text(
    review_item: Any,
) -> str:
    """
    Extract text from supported review formats.

    Supported examples:

    - plain string
    - {"text": "..."}
    - {"text": {"ar": "..."}}
    - {"text": {"en": "..."}}
    - stringified dictionary
    """

    if isinstance(
        review_item,
        str,
    ):
        return _clean_review_text(
            review_item
        )

    if not isinstance(
        review_item,
        dict,
    ):
        return ""

    text = review_item.get(
        "text",
        "",
    )

    if isinstance(
        text,
        dict,
    ):
        selected_text = (
            text.get("ar")
            or text.get("en")
            or next(
                (
                    value
                    for value in text.values()
                    if isinstance(
                        value,
                        str,
                    )
                    and value.strip()
                ),
                "",
            )
        )

        return _clean_review_text(
            str(selected_text)
        )

    if isinstance(
        text,
        str,
    ):
        return _clean_review_text(
            text
        )

    return ""


def _clean_review_text(
    text: str,
) -> str:
    """
    Clean Review text while preserving its meaning.

    Operations:

    - Parse supported stringified dictionaries.
    - Replace escaped and real newlines.
    - Collapse repeated whitespace.
    """

    if not text:
        return ""

    cleaned = str(
        text
    ).strip()

    if (
        cleaned.startswith("{")
        and (
            "'ar'" in cleaned
            or '"ar"' in cleaned
            or "'en'" in cleaned
            or '"en"' in cleaned
        )
    ):
        try:
            parsed = ast.literal_eval(
                cleaned
            )

            if isinstance(
                parsed,
                dict,
            ):
                cleaned = str(
                    parsed.get("ar")
                    or parsed.get("en")
                    or ""
                )
        except (
            ValueError,
            SyntaxError,
        ):
            pass

    cleaned = cleaned.replace(
        "\\n",
        " ",
    ).replace(
        "\n",
        " ",
    )

    cleaned = " ".join(
        cleaned.split()
    )

    return cleaned.strip()