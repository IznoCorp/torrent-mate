"""Shared contracts for API providers.

Implements DESIGN §3.1: AuthMode, ApiError, CircuitOpenError, MediaType,
ProviderName. ApiError is a unified exception replacing all
provider-specific error types.

``ApiError``, ``CircuitOpenError`` and ``MediaType`` are now defined in the
lowest layer (``personalscraper.core._contracts``) and re-exported here for
backward compatibility (arch-cleanup-2 Phase 2). ``AuthMode``, ``ProviderName``,
``Named``/``HasName`` and ``TVDB_BOOTSTRAP`` remain defined in this module.
"""

from enum import Enum
from typing import Final, Protocol, runtime_checkable

# Re-export from the canonical core-layer home (arch-cleanup-2 Phase 2).
# All 35 downstream importers of personalscraper.api._contracts continue to work
# unchanged — the symbols are still accessible via this path. ``ApiError`` and
# ``CircuitOpenError`` and ``MediaType`` are now defined in core/_contracts.py
# (the lowest layer, no upward dependencies). Identity is preserved: the class
# objects imported here are the *same* objects as in core._contracts.
from personalscraper.core._contracts import (
    ApiError as ApiError,
)
from personalscraper.core._contracts import (
    CircuitOpenError as CircuitOpenError,
)
from personalscraper.core._contracts import (
    MediaType as MediaType,
)


class ProviderName(str, Enum):
    """Canonical lowercase provider identifiers.

    Constants for use in ``provider_name`` ClassVars, ``TransportPolicy``,
    ``ApiError``, and any other site that previously used a magic string.
    Inherits from ``str`` so existing comparisons and dict-key usage keep
    working unchanged. ``__str__`` returns the wire value to preserve
    f-string formatting parity with plain strings.
    """

    TMDB = "tmdb"
    TVDB = "tvdb"
    OMDB = "omdb"
    TRAKT = "trakt"
    QBITTORRENT = "qbittorrent"
    TRANSMISSION = "transmission"
    LACALE = "lacale"
    C411 = "c411"
    TELEGRAM = "telegram"
    HEALTHCHECKS = "healthchecks"

    def __str__(self) -> str:
        return str(self.value)


# Convenience constants for individual provider variants that need a
# distinguishing suffix (e.g. TVDB has a separate bootstrap-login policy).
TVDB_BOOTSTRAP: Final = "tvdb-bootstrap"


class AuthMode(Enum):
    """Authentication mode for API providers."""

    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    LOGIN = "login"
    NONE = "none"


@runtime_checkable
class Named(Protocol):
    """Capability marker exposing a stable ``provider_name`` identifier.

    Every API client — metadata, tracker, torrent, notify — declares its
    canonical lowercase name via a class-level ``provider_name`` attribute.
    This protocol lets helpers (``gather_ratings``, ``gather_cross_refs``,
    ``ProviderRegistry.get`` / ``providers_for``) filter heterogeneous
    provider collections without importing concrete client classes.

    The attribute holds the wire string (e.g. ``"tmdb"``) rather than the
    :class:`ProviderName` enum member so that ``Named`` stays agnostic of
    the enum and remains satisfied by both ``str`` and ``ProviderName``
    values — ``ProviderName`` inherits from ``str``.

    History: this Protocol was introduced twice — once here (originally
    ``HasName``) for the api/ layer, once in ``api/metadata/registry/``
    (as ``Named`` with ``ClassVar[str]``). PR review cycle 4 (finding I6)
    consolidated the two into this single ``@runtime_checkable`` Protocol
    living in the api/ contract layer; the registry now re-imports it.
    Declaring ``provider_name: str`` (not ``ClassVar[str]``) matches both
    instance-attribute and class-attribute providers — class attributes
    structurally satisfy a Protocol that declares an instance attribute.
    """

    provider_name: str


# Backward-compatibility alias for any external caller that still imports
# the pre-cycle-4 name. The canonical name is :class:`Named`.
HasName = Named
