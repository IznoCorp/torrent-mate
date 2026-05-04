"""Shared contracts for API providers.

Implements DESIGN §3.1: AuthMode, ApiError, CircuitOpenError.
ApiError is a unified exception replacing all provider-specific error types.
"""

from dataclasses import dataclass
from enum import Enum


class AuthMode(Enum):
    """Authentication mode for API providers."""

    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    LOGIN = "login"
    NONE = "none"


@dataclass
class ApiError(Exception):
    """Unified API error. Replaces TMDBError / TVDBError / etc.

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
