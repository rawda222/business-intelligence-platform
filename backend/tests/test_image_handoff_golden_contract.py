"""
Image Generation Handoff Golden Contract Tests
"""

import json
from pathlib import Path

from scripts.generate_image_handoff_golden import (
    build_handoff_payload,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "creative_context"
    / "image_handoff_v1.json"
)


def _load_fixture() -> dict:
    """Load the reviewed image-handoff fixture."""

    return json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )


def test_image_handoff_matches_golden_contract():
    """The image-team response must match the reviewed fixture."""

    expected = _load_fixture()

    actual = build_handoff_payload()

    assert actual == expected


def test_image_handoff_has_expected_root_contract():
    """The handoff should expose only approved root fields."""

    payload = _load_fixture()

    assert set(
        payload.keys()
    ) == {
        "contract_version",
        "business_id",
        "resolution_id",
        "generated_at",
        "campaign_date",
        "target_country_code",
        "platform",
        "content_format",
        "objective",
        "product_context",
        "theme",
        "fallback",
        "evidence_references",
    }


def test_image_handoff_excludes_internal_diagnostics():
    """Internal resolution data must not reach image services."""

    payload = _load_fixture()

    serialized = json.dumps(
        payload
    )

    excluded_fields = [
        "warnings",
        "resolved_moments",
        "rejected_moments",
        "social_platform_context",
        "automatic_context",
        "usable_account_ids",
    ]

    for field_name in excluded_fields:
        assert field_name not in serialized


def test_image_handoff_contains_selected_visual_direction():
    """The handoff should contain the selected visual direction."""

    payload = _load_fixture()

    theme = payload["theme"]

    assert theme is not None

    assert theme["theme_key"] == "summer"

    assert theme["business_fit"] == "high"

    assert theme["status"] == "active"

    assert (
        theme["creative_direction"][
            "visual_tokens"
        ]
    )

    assert (
        theme["constraints"][
            "brand_rules"
        ]
    )


def test_image_handoff_evidence_is_unique():
    """Evidence references should be unique and ordered."""

    payload = _load_fixture()

    evidence = payload[
        "evidence_references"
    ]

    assert len(evidence) == len(
        set(evidence)
    )

    assert evidence == [
        "country-profile:SA:1",
        "moment-definition:summer:1",
        (
            "business-context:"
            "aaaaaaaa-aaaa-aaaa-"
            "aaaa-aaaaaaaaaaaa"
        ),
    ]