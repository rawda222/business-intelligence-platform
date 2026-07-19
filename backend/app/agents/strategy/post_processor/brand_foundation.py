"""
Brand Strategy Foundation Post-Processor

Validates all brand-strategy sections against the approved SWOT
item IDs that Strategy Agent was authorized to consume.

Unsupported sections are removed rather than passed downstream.
Unknown source IDs are never preserved.
"""

from collections.abc import Mapping
from typing import Any

from app.agents.strategy.schemas.brand_foundation import (
    AudienceSegment,
    BrandStrategyFoundation,
    ChannelStrategy,
    ContentPillarStrategy,
    PositioningStrategy,
    StrategyGoal,
    ToneOfVoiceStrategy,
    ValuePropositionStrategy,
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
    """Return list-like values safely."""

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


def _valid_source_ids(
    payload: dict[str, Any],
    valid_item_ids: set[str],
) -> list[str]:
    """Keep only known approved SWOT item IDs."""

    result: list[str] = []

    for raw_item_id in _as_list(
        payload.get(
            "source_swot_item_ids"
        )
    ):
        if not isinstance(
            raw_item_id,
            str,
        ):
            continue

        item_id = raw_item_id.strip()

        if (
            item_id
            and item_id in valid_item_ids
            and item_id not in result
        ):
            result.append(
                item_id
            )

    return result


def _grounded_single(
    *,
    raw_value: Any,
    valid_item_ids: set[str],
    model_type: Any,
) -> Any:
    """Build one grounded section or return its empty default."""

    payload = _as_mapping(
        raw_value
    )

    source_ids = _valid_source_ids(
        payload,
        valid_item_ids,
    )

    if not source_ids:
        return model_type()

    payload[
        "source_swot_item_ids"
    ] = source_ids

    try:
        return model_type.model_validate(
            payload
        )
    except Exception:
        return model_type()


def _grounded_list(
    *,
    raw_value: Any,
    valid_item_ids: set[str],
    model_type: Any,
) -> list[Any]:
    """Build grounded list entries and discard unsupported ones."""

    result: list[Any] = []

    for raw_item in _as_list(
        raw_value
    ):
        payload = _as_mapping(
            raw_item
        )

        source_ids = _valid_source_ids(
            payload,
            valid_item_ids,
        )

        if not source_ids:
            continue

        payload[
            "source_swot_item_ids"
        ] = source_ids

        try:
            result.append(
                model_type.model_validate(
                    payload
                )
            )
        except Exception:
            continue

    return result


def build_brand_strategy_foundation(
    parsed: Any,
    valid_item_ids: set[str],
) -> BrandStrategyFoundation:
    """
    Build the seven grounded brand-strategy sections.

    Every retained section must reference at least one approved
    SWOT item visible to the Strategy Agent.
    """

    payload = _as_mapping(
        parsed
    )

    return BrandStrategyFoundation(
        positioning=_grounded_single(
            raw_value=payload.get(
                "positioning"
            ),
            valid_item_ids=(
                valid_item_ids
            ),
            model_type=(
                PositioningStrategy
            ),
        ),
        audience=_grounded_list(
            raw_value=payload.get(
                "audience"
            ),
            valid_item_ids=(
                valid_item_ids
            ),
            model_type=AudienceSegment,
        ),
        value_proposition=(
            _grounded_single(
                raw_value=payload.get(
                    "value_proposition"
                ),
                valid_item_ids=(
                    valid_item_ids
                ),
                model_type=(
                    ValuePropositionStrategy
                ),
            )
        ),
        tone_of_voice=(
            _grounded_single(
                raw_value=payload.get(
                    "tone_of_voice"
                ),
                valid_item_ids=(
                    valid_item_ids
                ),
                model_type=(
                    ToneOfVoiceStrategy
                ),
            )
        ),
        content_pillars=_grounded_list(
            raw_value=payload.get(
                "content_pillars"
            ),
            valid_item_ids=(
                valid_item_ids
            ),
            model_type=(
                ContentPillarStrategy
            ),
        ),
        channels=_grounded_list(
            raw_value=payload.get(
                "channels"
            ),
            valid_item_ids=(
                valid_item_ids
            ),
            model_type=ChannelStrategy,
        ),
        goals=_grounded_list(
            raw_value=payload.get(
                "goals"
            ),
            valid_item_ids=(
                valid_item_ids
            ),
            model_type=StrategyGoal,
        ),
    )