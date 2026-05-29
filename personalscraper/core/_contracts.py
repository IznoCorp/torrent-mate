"""Core-layer primitive contracts: errors and media type.

These symbols are defined here (the lowest layer) and re-exported from
``personalscraper.api._contracts`` for backward compatibility. This module
may only import from the Python standard library and ``enum`` — no upward
dependencies on ``api/``, ``conf/``, or any sibling personalscraper package.

Implements arch-cleanup-2 Phase 2 (layering relocation).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
        """Return the wire value (e.g. ``'movie'``)."""
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


@dataclass
class ApiError(Exception):
    """Unified API error raised by every provider on transport or response failure.

    Uses ``@dataclass`` to match the existing definition in ``api/_contracts.py``
    and preserve the auto-generated ``__eq__`` that tests rely on.
    ``dataclasses`` is stdlib — no upward dependency introduced.

    Attributes:
        provider: Provider name (e.g. ``"TMDB"``, ``"TVDB"``).
        http_status: HTTP status code from the response.
        provider_code: Provider-specific error code, if any.
        message: Human-readable error message.
    """

    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

    def __str__(self) -> str:
        """Return a concise error string."""
        code = f" provider_code={self.provider_code}" if self.provider_code else ""
        return f"{self.provider} API {self.http_status}{code}: {self.message}"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit.

    Attributes:
        provider: Name of the unavailable provider.
        remaining_seconds: Seconds remaining until cooldown expires.
    """

    def __init__(self, provider: str, remaining_seconds: float) -> None:
        """Initialise CircuitOpenError.

        Args:
            provider: Name of the unavailable provider.
            remaining_seconds: Seconds until the circuit may transition to HALF_OPEN.
        """
        self.provider = provider
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Circuit breaker OPEN for {provider} ({remaining_seconds:.0f}s remaining)")
