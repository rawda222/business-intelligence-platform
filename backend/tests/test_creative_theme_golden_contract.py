"""
Automatic Creative Theme Golden Contract Test
"""

import json
from pathlib import Path

from scripts.generate_creative_theme_golden import (
    build_payload,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "creative_context"
    / "automatic_theme_response_v1.json"
)


def test_automatic_theme_response_matches_golden_contract():
    """
    The public image-team response must match the reviewed fixture.

    An intentional contract change requires regenerating and
    reviewing the fixture before committing it.
    """

    expected = json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )

    actual = build_payload()

    assert actual == expected


def test_golden_contract_identifies_version_one():
    """The fixture must remain explicitly versioned."""

    payload = json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["theme_result"][
            "contract_version"
        ]
        == "1.0"
    )


def test_golden_contract_is_fully_automatic():
    """The fixture must represent the automatic workflow."""

    payload = json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["automatic_context"][
            "request"
        ]["selection_mode"]
        == "automatic"
    )

    assert (
        payload["automatic_context"][
            "platform"
        ]["source"]
        == "connected_platform_policy"
    )


def test_golden_contract_contains_image_team_theme():
    """The fixture must include the selected visual theme."""

    payload = json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )

    primary_theme = (
        payload["theme_result"][
            "primary_theme"
        ]
    )

    assert primary_theme is not None

    assert (
        primary_theme["theme_key"]
        == "summer"
    )

    assert (
        primary_theme[
            "creative_direction"
        ]["visual_tokens"]
    )