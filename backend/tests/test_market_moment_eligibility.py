"""
Market Moment Business Eligibility Tests
"""

from app.creative_context.country_registry import (
    load_default_country_registry,
)
from app.creative_context.eligibility import (
    evaluate_moment_eligibility,
    is_country_applicable,
    is_objective_supported,
    resolve_business_fit,
)
from app.creative_context.moment_registry import (
    load_default_moment_registry,
)


def test_summer_has_high_fit_for_food_and_beverage():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "SA"
        ),
        business_type=(
            "food_and_beverage"
        ),
        objective="awareness",
    )

    assert result.country_applicable is True

    assert (
        result.objective_supported
        is True
    )

    assert result.business_fit == "high"

    assert (
        result.automatically_eligible
        is True
    )


def test_summer_has_medium_fit_for_retail():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "AE"
        ),
        business_type="retail",
        objective="engagement",
    )

    assert result.business_fit == "medium"

    assert (
        result.automatically_eligible
        is True
    )


def test_summer_low_fit_is_not_automatic():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "SA"
        ),
        business_type="saas",
        objective="awareness",
    )

    assert result.business_fit == "low"

    assert (
        result.automatically_eligible
        is False
    )

    assert any(
        "not selected automatically"
        in reason
        for reason in result.reasons
    )


def test_excluded_business_is_not_applicable():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "SA"
        ),
        business_type="b2b_services",
        objective="awareness",
    )

    assert (
        result.business_fit
        == "not_applicable"
    )

    assert (
        result.automatically_eligible
        is False
    )


def test_saudi_national_day_is_not_applicable_to_uae():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "saudi_national_day"
        ),
        country=country_registry.get(
            "AE"
        ),
        business_type="retail",
        objective="awareness",
    )

    assert (
        result.country_applicable
        is False
    )

    assert (
        result.automatically_eligible
        is False
    )


def test_uae_national_day_is_applicable_to_uae():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    assert is_country_applicable(
        moment=moment_registry.get(
            "uae_national_day"
        ),
        country=country_registry.get(
            "AE"
        ),
    )


def test_sales_only_moment_rejects_awareness_objective():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "white_friday"
        ),
        country=country_registry.get(
            "SA"
        ),
        business_type="retail",
        objective="awareness",
    )

    assert (
        result.objective_supported
        is False
    )

    assert (
        result.automatically_eligible
        is False
    )


def test_sales_only_moment_accepts_sales_objective():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    assert is_objective_supported(
        moment=moment_registry.get(
            "white_friday"
        ),
        objective="sales",
    )


def test_unknown_business_type_is_not_applicable():
    moment_registry = (
        load_default_moment_registry()
    )

    fit = resolve_business_fit(
        moment=moment_registry.get(
            "summer"
        ),
        business_type=(
            "unknown_business_type"
        ),
    )

    assert fit == "not_applicable"


def test_country_and_objective_are_normalized():
    country_registry = (
        load_default_country_registry()
    )

    moment_registry = (
        load_default_moment_registry()
    )

    result = evaluate_moment_eligibility(
        moment=moment_registry.get(
            "summer"
        ),
        country=country_registry.get(
            "sa"
        ),
        business_type=(
            " FOOD_AND_BEVERAGE "
        ),
        objective=" AWARENESS ",
    )

    assert result.business_fit == "high"

    assert (
        result.automatically_eligible
        is True
    )