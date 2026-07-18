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

class MomentRegistryError(
    CreativeContextError
):
    """Market-moment registry configuration is invalid."""


class MomentNotFoundError(
    MomentRegistryError
):
    """Requested market moment is missing or disabled."""


class DuplicateMomentKeyError(
    MomentRegistryError
):
    """Multiple market moments use the same key."""
class MomentDateResolutionError(
    CreativeContextError
):
    """A market-moment date window could not be resolved."""


class MomentDateOverrideError(
    MomentDateResolutionError
):
    """A moment date override is invalid or conflicting."""