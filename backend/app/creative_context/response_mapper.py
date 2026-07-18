"""
Automatic Creative Theme Response Mapper

Converts internal dataclass orchestration results into the stable
Pydantic contract returned by the FastAPI endpoint.
"""

from app.creative_context.automatic_service import (
    AutomaticCreativeThemeResult,
)
from app.creative_context.schemas import (
    AutoContextFieldResponse,
    AutomaticCampaignContextResponse,
    AutomaticCreativeThemeResponse,
    SocialPlatformContextResponse,
)


def _map_field(
    *,
    value: str,
    source: str,
    confidence: float,
) -> AutoContextFieldResponse:
    """Map one automatic field into its public contract."""

    return AutoContextFieldResponse(
        value=value,
        source=source,
        confidence=confidence,
    )


def map_automatic_creative_theme_response(
    result: AutomaticCreativeThemeResult,
) -> AutomaticCreativeThemeResponse:
    """Map the internal result into the public API response."""

    context = result.automatic_context

    automatic_context = (
        AutomaticCampaignContextResponse(
            request=context.request,
            campaign_date=_map_field(
                value=context.campaign_date.value,
                source=context.campaign_date.source,
                confidence=(
                    context.campaign_date.confidence
                ),
            ),
            target_country_code=_map_field(
                value=(
                    context
                    .target_country_code
                    .value
                ),
                source=(
                    context
                    .target_country_code
                    .source
                ),
                confidence=(
                    context
                    .target_country_code
                    .confidence
                ),
            ),
            platform=_map_field(
                value=context.platform.value,
                source=context.platform.source,
                confidence=(
                    context.platform.confidence
                ),
            ),
            content_format=_map_field(
                value=(
                    context.content_format.value
                ),
                source=(
                    context.content_format.source
                ),
                confidence=(
                    context.content_format.confidence
                ),
            ),
            objective=_map_field(
                value=context.objective.value,
                source=context.objective.source,
                confidence=(
                    context.objective.confidence
                ),
            ),
            product_context=_map_field(
                value=(
                    context.product_context.value
                ),
                source=(
                    context.product_context.source
                ),
                confidence=(
                    context.product_context.confidence
                ),
            ),
            evidence_references=list(
                context.evidence_references
            ),
            warnings=list(
                context.warnings
            ),
        )
    )

    social_context = (
        result.social_platform_context
    )

    social_platform_context = (
        SocialPlatformContextResponse(
            platforms=list(
                social_context.platforms
            ),
            usable_account_ids=list(
                social_context
                .usable_account_ids
            ),
            warnings=list(
                social_context.warnings
            ),
        )
    )

    return AutomaticCreativeThemeResponse(
        theme_result=result.theme_result,
        automatic_context=(
            automatic_context
        ),
        social_platform_context=(
            social_platform_context
        ),
    )