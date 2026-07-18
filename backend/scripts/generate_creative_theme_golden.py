"""
Generate the automatic creative-theme golden contract fixture.

Run this script only when an intentional API contract change has
been reviewed and approved.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.creative_context.automatic_service import (
    resolve_automatic_creative_theme,
)
from app.creative_context.response_mapper import (
    map_automatic_creative_theme_response,
)
from app.models.pg.business import Business
from app.models.pg.social_account import (
    SocialAccount,
)


OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "creative_context"
    / "automatic_theme_response_v1.json"
)

BUSINESS_ID = UUID(
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
)

OWNER_ID = UUID(
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
)

ACCOUNT_ID = UUID(
    "cccccccc-cccc-cccc-cccc-cccccccccccc"
)

RESOLUTION_ID = UUID(
    "dddddddd-dddd-dddd-dddd-dddddddddddd"
)

FIXED_TIME = datetime(
    2026,
    7,
    18,
    9,
    0,
    tzinfo=UTC,
)


def build_business() -> Business:
    """Build the deterministic golden-contract business."""

    return Business(
        id=BUSINESS_ID,
        owner_id=OWNER_ID,
        name="Volume Cafe",
        business_type="food_and_beverage",
        industry="cafe",
        location="Riyadh",
        country_code="SA",
        business_metadata={
            "brand_rules": [
                "Preserve brand colors",
                "Keep packaging recognizable",
            ],
            "segment": "premium",
        },
        is_active=True,
    )


def build_account() -> SocialAccount:
    """Build the deterministic connected social account."""

    return SocialAccount(
        id=ACCOUNT_ID,
        business_id=BUSINESS_ID,
        platform="instagram",
        platform_account_id="golden-instagram-account",
        account_name="Volume Cafe",
        account_username="volume_cafe",
        connector_type="apify",
        account_metadata={},
        is_active=True,
        connection_status="connected",
        connected_at=FIXED_TIME,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


def build_payload() -> dict:
    """Build the stable public response payload."""

    internal_result = (
        resolve_automatic_creative_theme(
            business=build_business(),
            social_accounts=[
                build_account()
            ],
            current_time=FIXED_TIME,
            generated_at=FIXED_TIME,
            resolution_id=RESOLUTION_ID,
            max_secondary_moments=1,
        )
    )

    response = (
        map_automatic_creative_theme_response(
            internal_result
        )
    )

    return response.model_dump(
        mode="json"
    )


def main() -> None:
    """Write the reviewed golden response fixture."""

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            build_payload(),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Golden fixture written to: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()