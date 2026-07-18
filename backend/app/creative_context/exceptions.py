"""
Creative Context Exceptions
"""


class CreativeContextError(
    ValueError
):
    """Base error for creative-context operations."""


class CountryRegistryError(
    CreativeContextError
):
    """Country registry configuration is invalid."""


class CountryNotFoundError(
    CountryRegistryError
):
    """Requested country does not exist in the registry."""


class DuplicateCountryCodeError(
    CountryRegistryError
):
    """Multiple profiles use the same country code."""
