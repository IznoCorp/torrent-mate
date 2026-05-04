"""Transport policy contracts for API providers.

Implements DESIGN S3.3: RetryPolicy, CircuitPolicy, RateLimitPolicy,
AuthMethod Protocol, and TransportPolicy. Every provider declares HOW
it wants the transport to behave; the transport enforces it uniformly.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

import requests


@dataclass(frozen=True)
class RetryPolicy:
    """Tenacity retry configuration for transient errors.

    Attributes:
        max_attempts: Maximum number of attempts including the first call.
        initial_wait: Minimum wait in seconds before the first backoff step.
        max_wait: Maximum wait in seconds between attempts.
        retryable_statuses: HTTP status codes that trigger a retry.
    """

    max_attempts: int = 4
    initial_wait: float = 0.5
    max_wait: float = 10.0
    retryable_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class CircuitPolicy:
    """Circuit breaker configuration for durable provider failures.

    Attributes:
        failure_threshold: Consecutive failures before opening the circuit.
        cooldown_seconds: Seconds to wait in OPEN state before HALF_OPEN.
        count_retries: If False (default), only the final failure after retries
            exhaust increments the breaker. If True, every retry attempt counts.
    """

    failure_threshold: int = 5
    cooldown_seconds: float = 300.0
    count_retries: bool = False


@dataclass(frozen=True)
class RateLimitPolicy:
    """Rate limit configuration for the token-bucket limiter.

    Attributes:
        requests_per_second: Max requests per second. 0.0 = disabled.
    """

    requests_per_second: float = 0.0


class AuthMethod(Protocol):
    """Authentication declaration for a provider.

    Two responsibilities:
    - apply(session): one-time mutation at transport init (e.g. set
      Authorization header, set session.auth for Basic Auth).
    - auth_params(): per-request query params merged by HttpTransport
      (e.g. OMDB-style apikey=...). Returns {} for header-based auth.

    Token refresh is intentionally NOT part of this Protocol.
    """

    def apply(self, session: requests.Session) -> None: ...

    def auth_params(self) -> dict[str, str]: ...


@dataclass
class TransportPolicy:
    """Provider-declared transport behavior.

    HttpTransport is provider-agnostic and consumes this dataclass.
    Each provider exposes a policy() classmethod or module-level
    constant building this from credentials.

    Attributes:
        provider_name: Human-readable provider name (e.g. "TMDB").
        base_url: Base URL for all API calls (no trailing path).
        auth: AuthMethod implementation for this provider.
        timeout_seconds: Per-request timeout.
        retry: RetryPolicy for transient failures.
        circuit: CircuitPolicy for durable outage protection.
        rate_limit: RateLimitPolicy for throttling.
        extra_headers: Additional headers sent with every request.
        response_format: Expected response body format.
    """

    provider_name: str
    base_url: str
    auth: AuthMethod
    timeout_seconds: float = 10.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    circuit: CircuitPolicy = field(default_factory=CircuitPolicy)
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    extra_headers: dict[str, str] = field(default_factory=dict)
    response_format: Literal["json", "xml", "text"] = "json"
