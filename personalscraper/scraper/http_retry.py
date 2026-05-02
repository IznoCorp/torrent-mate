"""Shared HTTP retry predicates and callbacks for tenacity.

Provides factories to create retry predicates that handle provider-specific
errors (TMDBError, TVDBError) alongside standard requests exceptions, and
a shared before_sleep callback factory for structured warning logs.
Used by tmdb_client, tvdb_client, and artwork modules.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests.exceptions
from structlog.stdlib import BoundLogger
from tenacity import RetryCallState
from tenacity.wait import wait_base

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _parse_retry_after(header_value: str | None) -> float | None:
    """Parse the value of an HTTP ``Retry-After`` header.

    Accepts both forms permitted by RFC 7231:

    - integer seconds (``"42"``)
    - HTTP-date (``"Wed, 21 Oct 2026 07:28:00 GMT"``)

    Args:
        header_value: Raw ``Retry-After`` header value or ``None``.

    Returns:
        Number of seconds to wait, or ``None`` if the header is absent or
        malformed.
    """
    if header_value is None:
        return None
    header_value = header_value.strip()
    if not header_value:
        return None
    try:
        return max(0.0, float(header_value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header_value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = (when - datetime.now(tz=timezone.utc)).total_seconds()
    return max(0.0, delta)


def _retry_after_from_exception(exc: BaseException | None) -> float | None:
    """Pull a ``Retry-After`` seconds value from a retryable exception.

    Looks up the header on:
    - ``exc.response`` (requests.HTTPError carrying a Response).
    - ``exc.headers`` (provider-specific error type that surfaces headers
      directly, e.g. TMDBError / TVDBError).

    Returns ``None`` for exceptions that do not carry header information.
    """
    if exc is None:
        return None
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "headers", None) is not None:
        value = _parse_retry_after(response.headers.get("Retry-After"))
        if value is not None:
            return value
    headers = getattr(exc, "headers", None)
    if headers is not None:
        return _parse_retry_after(headers.get("Retry-After"))
    return None


class wait_with_retry_after(wait_base):
    """Tenacity wait strategy that honors ``Retry-After`` on 429 responses.

    Wraps a fallback wait strategy (typically ``wait_exponential_jitter`` or
    ``wait_exponential``).  When the last failure carries a ``Retry-After``
    header (parseable as either integer seconds or an HTTP-date), the parsed
    value is used as-is — clamped against an optional ``max_wait`` ceiling so
    pathological server responses (``Retry-After: 86400``) cannot stall the
    pipeline indefinitely.  Otherwise the fallback strategy decides.

    Args:
        fallback: Underlying wait strategy used when no Retry-After is
            present (or the parse fails).
        max_wait: Upper bound (seconds) applied to honored Retry-After
            values.  Defaults to 60s — well above typical TMDB/TVDB rate
            limits but low enough that a misbehaving server cannot freeze
            a scrape.
    """

    def __init__(self, fallback: wait_base, max_wait: float = 60.0) -> None:
        """Store the fallback strategy and ceiling."""
        self._fallback = fallback
        self._max_wait = max_wait

    def __call__(self, retry_state: RetryCallState) -> float:
        """Return the seconds to wait for ``retry_state``."""
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        retry_after = _retry_after_from_exception(exc)
        if retry_after is not None:
            return min(retry_after, self._max_wait)
        return float(self._fallback(retry_state))


def build_retry_logger(log: BoundLogger, event: str) -> Callable[[RetryCallState], None]:
    """Build a tenacity before_sleep callback that logs a warning via structlog.

    Extracts the exception (if any) from the retry state and emits a structured
    warning with the attempt number, the upcoming wait duration, and exc_info for
    traceback capture.

    When no exception is available (outcome absent, or outcome was a non-exception
    result), the callback logs with ``exc_info=False`` and ``error=None`` — no
    traceback, no error field.

    Args:
        log: Bound structlog logger for the calling module.
        event: structlog event name to use for the warning log entry.  Must be
            snake_case and follow the event-naming convention described in
            docs/reference/logging.md (event-naming-guideline section).

    Returns:
        Callback accepted by tenacity's before_sleep parameter.

    Note:
        exc_info is passed as the exception instance (or False), NOT as True.
        See RULE D in docs/reference/logging.md: tenacity before_sleep callbacks
        run outside the active except block, so sys.exc_info() is empty there.
        Passing the exception INSTANCE directly lets structlog render the
        traceback from it even when sys.exc_info() is (None, None, None).
    """

    def _cb(retry_state: RetryCallState) -> None:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        # RULE D: tenacity before_sleep runs outside the active except block;
        # sys.exc_info() is empty there. Pass the exception INSTANCE (or False)
        # so structlog can render the traceback.
        log.warning(
            event,
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep if retry_state.next_action else 0,
            exc_info=exc if exc is not None else False,
            error=str(exc) if exc is not None else None,
        )

    return _cb


def make_retryable_predicate(*provider_error_types: type) -> Callable[[BaseException], bool]:
    """Create a retry predicate for tenacity.

    Retries on:
    - Provider-specific errors with http_status in {429, 500, 502, 503, 504}
    - requests.HTTPError with status in {429, 500, 502, 503, 504}
    - Connection errors and timeouts

    Does NOT retry on 4xx client errors (401, 403, 404) or 501/505+.

    Args:
        *provider_error_types: Exception classes with an http_status attribute
            (e.g., TMDBError, TVDBError). Pass none for generic HTTP retry.

    Returns:
        A callable(BaseException) -> bool for retry_if_exception().
    """

    def _is_retryable(exc: BaseException) -> bool:
        for err_type in provider_error_types:
            if isinstance(exc, err_type):
                status = getattr(exc, "http_status", None)
                return status in _RETRYABLE_STATUS_CODES if status is not None else False
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

    return _is_retryable
