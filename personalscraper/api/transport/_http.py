"""HttpTransport — provider-agnostic HTTP client.

Implements DESIGN S3.7: consumes a TransportPolicy, enforces retry/circuit/
rate-limit/auth uniformly, and returns parsed responses based on response_format.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._policy import TransportPolicy
from personalscraper.api.transport._rate import RateLimiter
from personalscraper.core.circuit import CircuitBreaker
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus


class HttpTransport:
    """Provider-agnostic HTTP transport consuming a TransportPolicy.

    Enforces retry, circuit breaker, rate limiting, and auth uniformly
    for all API providers. Each provider declares its behavior via a
    TransportPolicy dataclass; HttpTransport is fully decoupled from
    any specific provider.

    Implements the context manager protocol so bootstrap flows (e.g.
    TVDB login) can deterministically close sessions.

    Attributes:
        _policy: The TransportPolicy declaring provider behavior.
    """

    def __init__(self, policy: TransportPolicy, *, event_bus: EventBus | None = None) -> None:
        """Initialize the HTTP transport from ``policy`` and thread ``event_bus``.

        Args:
            policy: The :class:`TransportPolicy` declaring provider behavior
                (auth, retry, circuit, rate limit).
            event_bus: Optional :class:`EventBus` forwarded to the internal
                :class:`CircuitBreaker` so transitions emit
                :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``.
                Optional in Phase 4 (additive contract); required in Phase 5.2.
        """
        self._policy = policy
        self._log = get_logger(f"api.{policy.provider_name.lower()}")

        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"
        for k, v in policy.extra_headers.items():
            self._session.headers[k] = v
        policy.auth.apply(self._session)

        self._circuit = CircuitBreaker(
            name=policy.provider_name,
            failure_threshold=policy.circuit.failure_threshold,
            cooldown_seconds=policy.circuit.cooldown_seconds,
            event_bus=event_bus,
        )
        self._rate_limiter = RateLimiter(policy.rate_limit.requests_per_second)

    # -- Public API ----------------------------------------------------------

    def get(self, path: str = "", params: dict[str, Any] | None = None) -> dict[str, Any] | str:
        """Send a GET request.

        Args:
            path: URL path appended to the base URL.
            params: Query parameters merged with auth params.

        Returns:
            Parsed response body (dict for json/xml, str for text).
        """
        return self._request_outer("GET", path, params=params)

    def post(self, path: str = "", data: dict[str, Any] | None = None) -> dict[str, Any] | str:
        """Send a POST request.

        Args:
            path: URL path appended to the base URL.
            data: JSON body sent as the request payload.

        Returns:
            Parsed response body (dict for json/xml, str for text).
        """
        return self._request_outer("POST", path, data=data)

    # -- Context manager -----------------------------------------------------

    def close(self) -> None:
        """Close the underlying requests session."""
        self._session.close()

    def __enter__(self) -> HttpTransport:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # -- Internal ------------------------------------------------------------

    def _request_outer(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        """Wrap the tenacity retry loop with circuit breaker gating.

        When count_retries=False (default), only the final failure after
        retries exhaust increments the circuit breaker. When True, each
        retry attempt inside _do_request counts.
        """
        self._circuit.guard()

        retry_decorator = retry(
            retry=retry_if_exception(self._is_retryable),
            wait=wait_exponential_jitter(
                initial=self._policy.retry.initial_wait,
                max=self._policy.retry.max_wait,
                jitter=0.5,
            ),
            stop=stop_after_attempt(self._policy.retry.max_attempts),
            reraise=True,
        )

        @retry_decorator
        def _attempt() -> dict[str, Any] | str:
            return self._do_request(method, path, params, data)

        try:
            result = _attempt()
        except Exception as exc:
            if not self._policy.circuit.count_retries:
                self._circuit.record_failure(exc)
            raise

        self._circuit.record_success()
        return result

    def _do_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
    ) -> dict[str, Any] | str:
        """Execute a single HTTP request.

        Auth query params are merged before every request so providers
        like OMDB (apikey in query string) work correctly.
        """
        self._rate_limiter.acquire()

        merged_params: dict[str, Any] = {**self._policy.auth.auth_params(), **(params or {})}
        url = f"{self._policy.base_url.rstrip('/')}{path}" if path else self._policy.base_url

        start = time.monotonic()
        resp = self._session.request(
            method,
            url,
            params=merged_params,
            json=data,
            timeout=self._policy.timeout_seconds,
        )
        duration = time.monotonic() - start
        self._log.debug(
            "api_call",
            provider=self._policy.provider_name,
            method=method,
            path=path,
            status=resp.status_code,
            duration_ms=int(duration * 1000),
        )

        if not resp.ok:
            try:
                err = resp.json()
            except ValueError:
                # Body is not JSON (often HTML from a proxy/gateway on 5xx).
                # Without this preview the resulting ApiError carries only
                # resp.reason and callers lose all context for upstream
                # debugging. Logged at warning (not debug) — volume is bounded
                # by the failure rate. ``url`` and ``method`` are included
                # because providers expose multiple endpoints and the body
                # preview alone won't pinpoint which one drifted.
                err = {}
                self._log.warning(
                    "api_error_body_unparsable",
                    provider=self._policy.provider_name,
                    method=method,
                    url=str(resp.url),
                    status=resp.status_code,
                    body_preview=resp.text[:200],
                )
            raise ApiError(
                provider=self._policy.provider_name,
                http_status=resp.status_code,
                provider_code=err.get("status_code", err.get("code", 0)),
                message=err.get("status_message", err.get("message", resp.reason)),
            )

        if self._policy.response_format == "json":
            return cast("dict[str, Any]", resp.json())
        if self._policy.response_format == "xml":
            import xmltodict  # type: ignore[import-untyped]

            return cast("dict[str, Any]", xmltodict.parse(resp.text))
        if self._policy.response_format == "text":
            return resp.text
        return cast("dict[str, Any]", resp.json())

    def _is_retryable(self, exc: BaseException) -> bool:
        """Determine if an exception should trigger a tenacity retry.

        Checks ApiError status codes against the policy's retryable_statuses
        and retries network-level failures (connection errors, timeouts).

        Args:
            exc: The exception raised by _do_request.

        Returns:
            True if the call should be retried.
        """
        retryable = self._policy.retry.retryable_statuses

        if isinstance(exc, ApiError):
            return exc.http_status in retryable

        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code in retryable

        return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
