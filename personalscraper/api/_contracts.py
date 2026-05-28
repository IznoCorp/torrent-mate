"""Shared contracts for API providers.

Implements DESIGN §3.1: AuthMode, ApiError, CircuitOpenError, MediaType,
ProviderName. ApiError is a unified exception replacing all
provider-specific error types.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, Protocol, runtime_checkable


class MediaType(str, Enum):
    """Canonical media type used across all metadata- and tracker-family APIs.

    Inherits from ``str`` so existing equality checks (``media_type == "tv"``),
    dict keys, and JSON serialization keep working unchanged — ``MediaType.TV``
    *is* the string ``"tv"``. New code should prefer the enum members for
    nominal typing and exhaustive ``match`` statements.

    The legacy library/dispatch/scraper layers historically used ``"tvshow"``
    instead of ``"tv"``; :meth:`from_legacy` is the single coercion entry
    point that maps both vocabularies into this enum.

    ``__str__`` returns the wire value (``"movie"`` / ``"tv"``) rather than the
    enum repr (``"MediaType.MOVIE"``). This matches Python 3.11+ ``StrEnum``
    semantics and keeps f-string interpolation backward-compatible with the
    previous ``Literal`` alias.
    """

    MOVIE = "movie"
    TV = "tv"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_legacy(cls, value: str) -> "MediaType":
        """Coerce any historical media-type string into a :class:`MediaType`.

        Accepts the api/ vocabulary (``"movie"``, ``"tv"``) and the legacy
        library/dispatch vocabulary (``"tvshow"``, ``"tvshows"``). Case- and
        whitespace-insensitive.

        Args:
            value: Free-form string from a legacy caller.

        Returns:
            The matching :class:`MediaType` enum member.

        Raises:
            ValueError: ``value`` is not a recognised media-type string.
        """
        normalised = value.strip().lower()
        if normalised == "movie":
            return cls.MOVIE
        if normalised in ("tv", "tvshow", "tvshows"):
            return cls.TV
        raise ValueError(f"Unknown media_type {value!r} — expected one of: 'movie', 'tv', 'tvshow', 'tvshows'.")


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


@dataclass
class ApiError(Exception):
    """Unified API error raised by every provider on transport or response failure.

    Attributes:
        provider: Provider name (e.g. "TMDB", "TVDB").
        http_status: HTTP status code from the response.
        provider_code: Provider-specific error code, if any.
        message: Human-readable error message.
    """

    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

    def __str__(self) -> str:
        code = f" provider_code={self.provider_code}" if self.provider_code else ""
        return f"{self.provider} API {self.http_status}{code}: {self.message}"


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


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit.

    Attributes:
        provider: Name of the unavailable provider.
        remaining_seconds: Seconds remaining until cooldown expires.
    """

    def __init__(self, provider: str, remaining_seconds: float) -> None:
        self.provider = provider
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Circuit breaker OPEN for {provider} ({remaining_seconds:.0f}s remaining)")
