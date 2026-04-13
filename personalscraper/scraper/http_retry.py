"""Shared HTTP retry predicates for tenacity.

Provides a factory to create retry predicates that handle provider-specific
errors (TMDBError, TVDBError) alongside standard requests exceptions.
Used by tmdb_client, tvdb_client, and artwork modules.
"""

from collections.abc import Callable

import requests.exceptions

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def make_retryable_predicate(*provider_error_types: type) -> Callable[[BaseException], bool]:
    """Create a retry predicate for tenacity.

    Retries on:
    - Provider-specific errors with http_status in {429, 500-504}
    - requests.HTTPError with status in {429, 500-504}
    - Connection errors and timeouts

    Does NOT retry on 4xx client errors (401, 403, 404).

    Args:
        *provider_error_types: Exception classes with an http_status attribute
            (e.g., TMDBError, TVDBError). Pass none for generic HTTP retry.

    Returns:
        A callable(BaseException) -> bool for retry_if_exception().
    """

    def _is_retryable(exc: BaseException) -> bool:
        for err_type in provider_error_types:
            if isinstance(exc, err_type):
                return exc.http_status in _RETRYABLE_STATUS_CODES
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

    return _is_retryable
