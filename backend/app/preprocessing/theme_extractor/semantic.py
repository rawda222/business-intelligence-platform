"""
AI Semantic Theme Extractor
===========================

Uses Gemini to group customer comments by business meaning,
then validates all evidence IDs using deterministic Python logic.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.agents.swot.enums import LLMProvider
from app.agents.swot.llm.chain import (
    LLMClientFactory,
    call_llm_chain,
)
from app.preprocessing.theme_extractor.reviews import (
    get_review_text,
)


ALLOWED_THEME_CATEGORIES = {
    "product_quality",
    "customer_demand",
    "permanent_menu_request",
    "product_availability",
    "service_experience",
    "pricing_perception",
    "brand_loyalty",
    "customer_experience",
    "product_safety",
    "competitive_risk",
    "reputation_risk",
    "product_preference",
    "other_business_theme",
}


GENERIC_THEME_NAMES = {
    "good",
    "omg",
    "wow",
    "nice",
    "amazing",
    "love",
    "want",
    "need",
    "perfect",
    "favorite",
    "emerging theme: good",
    "emerging theme: omg",
}


POSITIVE_CATEGORIES = {
    "product_quality",
    "brand_loyalty",
    "customer_experience",
    "product_preference",
}


NEGATIVE_CATEGORIES = {
    "service_experience",
    "pricing_perception",
    "product_safety",
    "reputation_risk",
}


OPPORTUNITY_CATEGORIES = {
    "customer_demand",
    "permanent_menu_request",
    "product_availability",
}


THREAT_CATEGORIES = {
    "product_safety",
    "competitive_risk",
    "reputation_risk",
}


SYSTEM_PROMPT = """
You are a business customer-voice analyst.

Your task is to group semantically similar customer records into
meaningful business themes.

Theme names must describe a real business concept, customer need,
product attribute, availability issue, customer-experience issue,
market opportunity, or risk.

Never use generic reaction words as theme names.

Forbidden theme names include:

good
omg
wow
nice
amazing
love
want
need
perfect
favorite

Examples:

"so good", "perfect", "my favorite", and "I love this"
must be grouped under a theme such as:

Product Taste and Quality

"permanent item", "I want this", "I need this", and
"customers waited years"
must be grouped under:

Strong Product Demand

or:

Permanent Menu Requests

"available in Canada" and "available at Target"
must be grouped under:

Regional Product Availability

Use only the record IDs provided in the input.
Never invent evidence IDs, quotations, customer statements,
competitors, or business claims.

A serious concern supported by only one record may be returned,
but it must set:

requires_manual_review = true

A customer allegation must not be presented as a verified fact.

Choose theme_category from this exact list only:

product_quality
customer_demand
permanent_menu_request
product_availability
service_experience
pricing_perception
brand_loyalty
customer_experience
product_safety
competitive_risk
reputation_risk
product_preference
other_business_theme

Sentiment must be one of:

positive
negative
neutral
mixed

Return valid JSON only, using this exact structure:

{
  "themes": [
    {
      "theme_name": "Product Taste and Quality",
      "theme_category": "product_quality",
      "summary": "Customers positively discuss product taste.",
      "sentiment": "positive",
      "mention_ids": ["record-id-1"],
      "confidence_score": 0.85,
      "requires_manual_review": false
    }
  ]
}
""".strip()


def _business_name(
    data: Dict[str, Any],
) -> str:
    profile = data.get(
        "business_profile",
        {},
    )

    identity = profile.get(
        "business_identity",
        {},
    )

    return str(
        identity.get(
            "business_name",
            "Unknown Business",
        )
    )


def _record_id(
    review: Dict[str, Any],
) -> str:
    value = (
        review.get("review_id")
        or review.get("record_id")
        or review.get("id")
    )

    return str(value or "").strip()


def _entity_type(
    review: Dict[str, Any],
) -> str:
    value = review.get(
        "entity_type",
        "target_business",
    )

    return str(
        value or "target_business"
    )


def _source(
    review: Dict[str, Any],
) -> str:
    return str(
        review.get("source")
        or review.get("platform")
        or "unknown"
    )


def _date(
    review: Dict[str, Any],
) -> str | None:
    value = (
        review.get("date")
        or review.get("published_at")
        or review.get("created_at")
    )

    if value is None:
        return None

    isoformat = getattr(
        value,
        "isoformat",
        None,
    )

    if callable(isoformat):
        return str(isoformat())

    return str(value)


def _build_records(
    reviews: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    for review in reviews:
        record_id = _record_id(review)
        text = get_review_text(review).strip()

        if not record_id or not text:
            continue

        records.append(
            {
                "record_id": record_id,
                "entity_type": _entity_type(
                    review
                ),
                "source": _source(review),
                "date": _date(review),
                "text": text,
            }
        )

    return records


def _extract_json_object(
    raw_response: str,
) -> Dict[str, Any]:
    text = raw_response.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Semantic theme extraction returned "
            "invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "Semantic theme extraction must return "
            "a JSON object."
        )

    return parsed


def _normalize_category(
    value: Any,
) -> str:
    category = (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if category not in ALLOWED_THEME_CATEGORIES:
        return "other_business_theme"

    return category


def _normalize_sentiment(
    value: Any,
) -> str:
    sentiment = str(
        value or "neutral"
    ).strip().lower()

    if sentiment not in {
        "positive",
        "negative",
        "neutral",
        "mixed",
    }:
        return "neutral"

    return sentiment


def _normalize_confidence(
    value: Any,
) -> float:
    try:
        confidence = float(value)
    except (
        TypeError,
        ValueError,
    ):
        confidence = 0.5

    return round(
        max(
            0.0,
            min(1.0, confidence),
        ),
        2,
    )


def _validate_ai_themes(
    *,
    payload: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    record_map = {
        record["record_id"]: record
        for record in records
    }

    allowed_ids = set(record_map)

    raw_themes = payload.get(
        "themes",
        [],
    )

    if not isinstance(raw_themes, list):
        raise ValueError(
            "The AI themes field must be a list."
        )

    validated: List[Dict[str, Any]] = []

    seen_concepts: set[
        tuple[str, tuple[str, ...]]
    ] = set()

    for raw_theme in raw_themes:
        if not isinstance(
            raw_theme,
            dict,
        ):
            continue

        theme_name = str(
            raw_theme.get(
                "theme_name",
                "",
            )
        ).strip()

        if len(theme_name) < 3:
            continue

        if (
            theme_name.lower()
            in GENERIC_THEME_NAMES
        ):
            continue

        raw_ids = raw_theme.get(
            "mention_ids",
            [],
        )

        if not isinstance(raw_ids, list):
            continue

        mention_ids = list(
            dict.fromkeys(
                str(record_id)
                for record_id in raw_ids
                if str(record_id)
                in allowed_ids
            )
        )

        if not mention_ids:
            continue

        category = _normalize_category(
            raw_theme.get(
                "theme_category"
            )
        )

        sentiment = _normalize_sentiment(
            raw_theme.get("sentiment")
        )

        manual_review = bool(
            raw_theme.get(
                "requires_manual_review",
                False,
            )
        )

        if (
            category
            in {
                "product_safety",
                "competitive_risk",
                "reputation_risk",
            }
            and len(mention_ids) < 2
        ):
            manual_review = True

        duplicate_key = (
            category,
            tuple(sorted(mention_ids)),
        )

        if duplicate_key in seen_concepts:
            continue

        seen_concepts.add(
            duplicate_key
        )

        quotes = [
            record_map[record_id][
                "text"
            ]
            for record_id in mention_ids
        ][:3]

        entity_types = {
            record_map[record_id][
                "entity_type"
            ]
            for record_id in mention_ids
        }

        entity_type = (
            entity_types.pop()
            if len(entity_types) == 1
            else "mixed"
        )

        sentiment_distribution = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "mixed": 0,
        }

        sentiment_distribution[
            sentiment
        ] = len(mention_ids)

        validated.append(
            {
                "theme_name": theme_name,
                "theme_category": (
                    category
                ),
                "entity_type": (
                    entity_type
                ),
                "mentions": mention_ids,
                "frequency_count": len(
                    mention_ids
                ),
                "sentiment_distribution": (
                    sentiment_distribution
                ),
                "representative_quotes": (
                    quotes
                ),
                "confidence_score": (
                    _normalize_confidence(
                        raw_theme.get(
                            "confidence_score"
                        )
                    )
                ),
                "comparative_signal": (
                    "not_applicable"
                ),
                "summary": str(
                    raw_theme.get(
                        "summary",
                        "",
                    )
                ).strip(),
                "requires_manual_review": (
                    manual_review
                ),
                "_is_predefined": False,
                "_entity_names": [],
            }
        )

    if not validated:
        raise ValueError(
            "Gemini produced no usable "
            "business-relevant themes."
        )

    return validated


def extract_semantic_theme_records(
    *,
    data: Dict[str, Any],
    reviews: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    records = _build_records(
        reviews
    )

    if not records:
        raise ValueError(
            "No usable review records were "
            "available for semantic extraction."
        )

    user_prompt = json.dumps(
        {
            "business_name": (
                _business_name(data)
            ),
            "records": records,
        },
        ensure_ascii=False,
        indent=2,
    )

    chain = (
        LLMClientFactory.build_chain(
            preferred=(
                LLMProvider.VERTEX_AI
            ),
            model="gemini-2.5-flash",
        )
    )

    raw_response, client = (
        call_llm_chain(
            chain,
            SYSTEM_PROMPT,
            user_prompt,
        )
    )

    if not raw_response or client is None:
        raise RuntimeError(
            "Gemini semantic theme extraction "
            "failed."
        )

    payload = _extract_json_object(
        raw_response
    )

    return _validate_ai_themes(
        payload=payload,
        records=records,
    )


def extract_semantic_signals(
    theme_records: List[
        Dict[str, Any]
    ],
) -> tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    def signal_summary(
        record: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "theme_name": record[
                "theme_name"
            ],
            "theme_category": record[
                "theme_category"
            ],
            "entity_type": record[
                "entity_type"
            ],
            "reason": reason,
            "frequency_count": record[
                "frequency_count"
            ],
            "sentiment_distribution": (
                record[
                    "sentiment_distribution"
                ]
            ),
            "confidence_score": record[
                "confidence_score"
            ],
            "mentions": record[
                "mentions"
            ],
            "requires_manual_review": (
                record.get(
                    "requires_manual_review",
                    False,
                )
            ),
        }

    positive: List[
        Dict[str, Any]
    ] = []

    negative: List[
        Dict[str, Any]
    ] = []

    opportunity: List[
        Dict[str, Any]
    ] = []

    threat: List[
        Dict[str, Any]
    ] = []

    for record in theme_records:
        if (
            record.get("entity_type")
            not in {
                "target_business",
                "mixed",
            }
        ):
            continue

        category = record[
            "theme_category"
        ]

        sentiment = max(
            record[
                "sentiment_distribution"
            ],
            key=record[
                "sentiment_distribution"
            ].get,
        )

        if (
            category
            in POSITIVE_CATEGORIES
            or sentiment == "positive"
        ):
            positive.append(
                signal_summary(
                    record,
                    "semantic_positive_signal",
                )
            )

        if (
            category
            in NEGATIVE_CATEGORIES
            or sentiment == "negative"
        ):
            negative.append(
                signal_summary(
                    record,
                    "semantic_negative_signal",
                )
            )

        if category in OPPORTUNITY_CATEGORIES:
            opportunity.append(
                signal_summary(
                    record,
                    "semantic_opportunity",
                )
            )

        if category in THREAT_CATEGORIES:
            threat.append(
                signal_summary(
                    record,
                    (
                        "unverified_risk_"
                        "requiring_review"
                    ),
                )
            )

    return (
        positive,
        negative,
        opportunity,
        threat,
    )