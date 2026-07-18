"""
Image Generation Handoff Mapper

Converts the full automatic creative-theme API response into the
compact contract consumed by image-generation services.

Audit-only data such as rejected moments, inactive candidates,
social-account identifiers, and registry warnings is intentionally
excluded.
"""

from app.creative_context.schemas import (
    AutomaticCreativeThemeResponse,
    ImageGenerationHandoff,
)


def _unique_strings(
    values: list[str],
) -> list[str]:
    """Remove duplicate strings while preserving their order."""

    result: list[str] = []

    for value in values:
        cleaned = value.strip()

        if (
 cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    return result


def map_image_generation_handoff(
    response: AutomaticCreativeThemeResponse,
) -> ImageGenerationHandoff:
    """Build the compact image-generation contract."""

    request = (
        response.automatic_context.request
    )

    primary_theme = (
        response.theme_result.primary_theme
    )

    evidence_references: list[str] = []

    if primary_theme is not None:
        evidence_references = (
            _unique_strings(
                list(
                    primary_theme
                    .evidence_references
                )
            )
        )

    return ImageGenerationHandoff(
        business_id=(
            response.theme_result.business_id
        ),
        resolution_id=(
            response.theme_result.resolution_id
        ),
        generated_at=(
            response.theme_result.generated_at
        ),
        campaign_date=(
            request.campaign_date
        ),
        target_country_code=(
            request.target_country_code
        ),
        platform=request.platform,
        content_format=(
            request.content_format
        ),
        objective=request.objective,
        product_context=(
            request.product_context
        ),
        theme=primary_theme,
        fallback=(
            response.theme_result.fallback
        ),
        evidence_references=(
            evidence_references
        ),
    )