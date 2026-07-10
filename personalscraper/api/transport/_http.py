"""HttpTransport — provider-agnostic HTTP client.

Implements DESIGN S3.7: consumes a TransportPolicy, enforces retry/circuit/
rate-limit/auth uniformly, and returns parsed responses based on response_format.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._policy import TransportPolicy
from personalscraper.api.transport._rate import RateLimiter
from personalscraper.core.circuit import CircuitBreaker
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

# Default cap for ``get_bytes`` streamed downloads (10 MiB). Torrent metainfo
# files are kilobytes; the cap is a defensive guard against a misbehaving
# tracker streaming an unbounded HTML error page in place of a ``.torrent``.
_DEFAULT_MAX_BYTES = 10_485_760

# Return type of the ``response_mapper`` threaded through ``_request_outer`` —
# ``dict | str`` for the search path, ``bytes`` for the download path.
_T = TypeVar("_T")


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

    def __init__(self, policy: TransportPolicy, *, event_bus: EventBus) -> None:
        """Initialize the HTTP transport from ``policy`` and thread ``event_bus``.

        Args:
            policy: The :class:`TransportPolicy` declaring provider behavior
                (auth, retry, circuit, rate limit).
            event_bus: Required :class:`EventBus` forwarded to the internal
                :class:`CircuitBreaker` so transitions emit
                :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``.
                Tests that don't care about emit can pass a fresh
                ``EventBus()`` with no subscribers.
        """
        self._policy = policy
        self._log = get_logger(f"api.{policy.provider_name.lower()}")

        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"
        for k, v in policy.extra_headers.items():
            self._session.headers[k] = v
        policy.auth.apply(self._session)

        self._circuit = CircuitBreaker(name=policy.provider_name, failure_threshold=policy.circuit.failure_threshold, cooldown_seconds=policy.circuit.cooldown_seconds, event_bus=event_bus)  # noqa: E501  # fmt: skip
        self._rate_limiter = RateLimiter(policy.rate_limit.requests_per_second)

        # Download circuit + limiter — used exclusively by get_bytes() (D3).
        # Named "<provider>-download" so CircuitBreakerOpened events stay
        # distinguishable from the search breaker, and a download 5xx never
        # opens (or is gated by) the search circuit.
        self._download_circuit = CircuitBreaker(
            name=f"{policy.provider_name}-download",
            failure_threshold=policy.circuit.failure_threshold,
            cooldown_seconds=policy.circuit.cooldown_seconds,
            event_bus=event_bus,
        )
        self._download_rate_limiter = RateLimiter(policy.rate_limit.requests_per_second)

    # -- Public API ----------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the provider name declared by the transport's policy.

        Public accessor so callers (e.g. the tracker→torrent fetch boundary)
        can read the provider name for error context without reaching into the
        private ``_policy`` attribute.

        Returns:
            The provider name from the underlying :class:`TransportPolicy`.
        """
        return self._policy.provider_name

    def get(self, path: str = "", params: dict[str, Any] | None = None) -> dict[str, Any] | str:
        """Send a GET request.

        Args:
            path: URL path appended to the base URL.
            params: Query parameters merged with auth params.

        Returns:
            Parsed response body (dict for json/xml, str for text).
        """
        return self._request_outer(
            "GET",
            path,
            circuit=self._circuit,
            rate_limiter=self._rate_limiter,
            response_mapper=self._format_response,
            params=params,
        )

    def post(self, path: str = "", data: dict[str, Any] | None = None) -> dict[str, Any] | str:
        """Send a POST request.

        Args:
            path: URL path appended to the base URL.
            data: JSON body sent as the request payload.

        Returns:
            Parsed response body (dict for json/xml, str for text).
        """
        return self._request_outer(
            "POST",
            path,
            circuit=self._circuit,
            rate_limiter=self._rate_limiter,
            response_mapper=self._format_response,
            data=data,
        )

    def get_bytes(self, url: str, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> bytes:
        """Download a raw binary body via a streamed GET, size-capped.

        Provider-agnostic binary fetch used to pull ``.torrent`` metainfo
        files (and similar small binaries). The response body is streamed and
        read incrementally so an oversized payload is aborted before it is
        fully buffered into memory.

        URL handling (D10): an absolute URL (``http://`` / ``https://``) is
        used verbatim; a relative URL is joined onto ``policy.base_url``.

        Auth (D9): the absolute/override URL is sent as-is — ``auth_params()``
        is **not** re-merged onto the query string. Session-header auth applied
        at init still applies. This avoids appending a duplicate ``apikey=``
        when the tracker download URL already carries its passkey/token.

        Isolation (D3): uses the dedicated download circuit + rate limiter, so
        a flaky download endpoint never opens (or is throttled by) the search
        breaker.

        Args:
            url: Absolute download URL, or a path relative to ``base_url``.
            max_bytes: Hard cap on the downloaded size in bytes. Exceeding it
                aborts the stream immediately.

        Returns:
            The raw response body as ``bytes`` (never parsed, regardless of
            ``policy.response_format``).

        Raises:
            ValueError: If the body is empty, or exceeds ``max_bytes``. This
                is a provider-agnostic error by design — the transport stays
                decoupled from any provider family. Callers (e.g. the torrent
                fetcher) map it to a domain-specific error.
            ApiError: If the server returns a non-2xx status.
            CircuitOpenError: If the download circuit is OPEN.
        """
        # D10: absolute URL verbatim; relative joined onto base_url.
        if url.lower().startswith(("http://", "https://")):
            full_url = url
        else:
            full_url = f"{self._policy.base_url.rstrip('/')}{url}"

        def _download_mapper(resp: requests.Response) -> bytes:
            """Stream the response body, enforcing the size cap and non-empty rule."""
            # ``stream=True`` keeps the underlying connection open until the body
            # is consumed or the response is closed. The oversize path raises
            # mid-stream, so close on EVERY exit (success, oversize, empty) to
            # avoid leaking the connection on the exact path defending against
            # an unbounded stream.
            try:
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    total += len(chunk)
                    if total > max_bytes:
                        # D5 oversize — agnostic ValueError, NOT a tracker error.
                        raise ValueError(f"download exceeds max_bytes={max_bytes}")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if not data:
                    # D5 empty — agnostic ValueError, NOT a tracker error.
                    raise ValueError("empty download body")
                return data
            finally:
                resp.close()

        return self._request_outer(
            "GET",
            "",
            circuit=self._download_circuit,
            rate_limiter=self._download_rate_limiter,
            response_mapper=_download_mapper,
            override_url=full_url,  # D9: skip auth_params() merge.
            stream=True,
        )

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
        circuit: CircuitBreaker,
        rate_limiter: RateLimiter,
        response_mapper: Callable[[requests.Response], _T],
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        override_url: str | None = None,
        stream: bool = False,
    ) -> _T:
        """Wrap the tenacity retry loop with circuit breaker gating.

        Parameterized over ``circuit``/``rate_limiter`` so the search path
        (``get``/``post``) and the download path (``get_bytes``) share the
        retry/circuit machinery without duplication while keeping their
        breakers and limiters isolated (D3). ``response_mapper`` turns the
        raw :class:`requests.Response` into the caller's return shape (parsed
        body for search, raw bytes for download).

        When ``count_retries=False`` (default), only the final failure after
        retries exhaust increments the circuit breaker. When True, each retry
        attempt inside ``_do_request_raw`` counts.

        Args:
            method: HTTP method.
            path: URL path appended to ``base_url`` (ignored when
                ``override_url`` is set).
            circuit: Circuit breaker gating this call (search vs download).
            rate_limiter: Rate limiter acquired before each attempt.
            response_mapper: Callable mapping the raw response to the result.
            params: Query parameters merged with auth params (search path).
            data: JSON body for the request (search path).
            override_url: Verbatim URL bypassing path-join and auth-param
                merge (download path, D9/D10).
            stream: Whether to stream the response body (download path, D5).

        Returns:
            The value produced by ``response_mapper``.
        """
        circuit.guard()

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
        def _attempt() -> _T:
            return self._do_request_raw(
                method,
                path,
                params,
                data,
                rate_limiter=rate_limiter,
                response_mapper=response_mapper,
                override_url=override_url,
                stream=stream,
            )

        start = time.monotonic()
        try:
            result = _attempt()
        except (ApiError, requests.RequestException) as exc:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            circuit._last_latency_ms = elapsed_ms
            if not self._policy.circuit.count_retries:
                circuit.record_failure(exc)
            raise

        elapsed_ms = (time.monotonic() - start) * 1000.0
        circuit._last_latency_ms = elapsed_ms
        circuit.record_success()
        return result

    def _do_request_raw(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        *,
        rate_limiter: RateLimiter,
        response_mapper: Callable[[requests.Response], _T],
        override_url: str | None = None,
        stream: bool = False,
    ) -> _T:
        """Execute a single HTTP request and map the response.

        Acquires ``rate_limiter`` inside the retry loop, builds the URL,
        sends the request, logs the call, raises :class:`ApiError` on non-2xx,
        then delegates the success path to ``response_mapper``.

        Auth query params are merged before every request so providers like
        OMDB (apikey in query string) work correctly — UNLESS ``override_url``
        is set, in which case the URL is used verbatim and ``auth_params()``
        is NOT merged (D9). Session-header auth applied at init still applies.

        Args:
            method: HTTP method.
            path: URL path appended to ``base_url`` (ignored if
                ``override_url`` is set).
            params: Query parameters merged with auth params.
            data: JSON body for the request.
            rate_limiter: Limiter acquired at the start of the call.
            response_mapper: Callable mapping the raw response to the result.
            override_url: Verbatim URL bypassing path-join + auth merge.
            stream: Whether to stream the response body.

        Returns:
            The value produced by ``response_mapper``.

        Raises:
            ApiError: If the server returns a non-2xx status.
        """
        rate_limiter.acquire()

        if override_url is not None:
            # D9: verbatim URL, no auth-param re-merge. ``requests`` would
            # otherwise append a second copy of any query key already present
            # (e.g. a tracker download URL carrying its own apikey/passkey).
            url = override_url
            merged_params: dict[str, Any] | None = None
        else:
            merged_params = {**self._policy.auth.auth_params(), **(params or {})}
            url = f"{self._policy.base_url.rstrip('/')}{path}" if path else self._policy.base_url

        start = time.monotonic()
        resp = self._session.request(
            method,
            url,
            params=merged_params,
            json=data,
            timeout=self._policy.timeout_seconds,
            stream=stream,
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
                message=err.get("status_message", err.get("message", err.get("Error", resp.reason))),
            )

        return response_mapper(resp)

    def _format_response(self, resp: requests.Response) -> dict[str, Any] | str:
        """Parse a successful response body per ``policy.response_format``.

        Default ``response_mapper`` for the search path (``get``/``post``).
        Extracted from the former ``_do_request`` tail so the download path
        can substitute a raw-bytes mapper without touching this logic.

        Args:
            resp: The successful (2xx) response.

        Returns:
            Parsed body — ``dict`` for json/xml, ``str`` for text.
        """
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
            exc: The exception raised by _do_request_raw.

        Returns:
            True if the call should be retried.
        """
        retryable = self._policy.retry.retryable_statuses

        if isinstance(exc, ApiError):
            return exc.http_status in retryable

        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code in retryable

        return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
