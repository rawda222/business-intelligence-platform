"""
Generate the image-generation handoff golden fixture.

Run this script only when an intentional image-team contract
change has been reviewed and approved.
"""

import json
from pathlib import Path

from app.creative_context.image_handoff_mapper import (
    map_image_generation_handoff,
)
from app.creative_context.schemas import (
    AutomaticCreativeThemeResponse,
)
from scripts.generate_creative_theme_golden import (
    build_payload,
)


OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "creative_context"
    / "image_handoff_v1.json"
)


def build_handoff_payload() -> dict:
    """Build the deterministic image-team contract."""

    full_response = (
        AutomaticCreativeThemeResponse
        .model_validate(
            build_payload()
        )
    )

    handoff = map_image_generation_handoff(
        full_response
    )

    return handoff.model_dump(
        mode="json"
    )


def main() -> None:
    """Write the reviewed image-handoff fixture."""

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            build_handoff_payload(),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Image handoff fixture written to: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()