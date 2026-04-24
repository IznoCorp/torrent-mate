"""Shared HTTP retry predicates and callbacks for tenacity.

Provides factories to create retry predicates that handle provider-specific
errors (TMDBError, TVDBError) alongside standard requests exceptions, and
a shared before_sleep callback factory for structured warning logs.
Used by tmdb_client, tvdb_client, and artwork modules.
"""

from collections.abc import Callable

import requests.exceptions
from structlog.stdlib import BoundLogger
from tenacity import RetryCallState

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def build_retry_logger(log: BoundLogger, event: str) -> Callable[[RetryCallState], None]:
    """Build a tenacity before_sleep callback that logs a warning via structlog.

    Extracts the exception (if any) from the retry state and emits a structured
    warning with the attempt number, the upcoming wait duration, and exc_info for
    traceback capture.

    When ``retry_state.outcome`` is ``None`` (tenacity calls before_sleep before
    the first outcome is recorded), the callback logs with ``exc_info=False`` and
    ``error=None`` — no traceback, no error field.

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
