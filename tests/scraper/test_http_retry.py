"""Tests for personalscraper.scraper.http_retry — shared retry predicates."""

import requests
import requests.exceptions
import requests.models

from personalscraper.scraper.http_retry import (
    make_retryable_predicate,
)


class _FakeProviderError(Exception):
    """Fake provider error with http_status for testing."""

    def __init__(self, http_status: int) -> None:
        self.http_status = http_status
        super().__init__(f"HTTP {http_status}")


class TestMakeRetryablePredicate:
    """Tests for make_retryable_predicate factory."""

    def test_provider_error_429_is_retryable(self) -> None:
        """Provider error with 429 (rate limit) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(429)) is True

    def test_provider_error_500_is_retryable(self) -> None:
        """Provider error with 500 (server error) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(500)) is True

    def test_provider_error_502_is_retryable(self) -> None:
        """Provider error with 502 (bad gateway) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(502)) is True

    def test_provider_error_404_not_retryable(self) -> None:
        """Provider error with 404 (not found) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(404)) is False

    def test_provider_error_401_not_retryable(self) -> None:
        """Provider error with 401 (unauthorized) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(401)) is False

    def test_connection_error_is_retryable(self) -> None:
        """requests.ConnectionError should always be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(requests.exceptions.ConnectionError()) is True

    def test_timeout_is_retryable(self) -> None:
        """requests.Timeout should always be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(requests.exceptions.Timeout()) is True

    def test_value_error_not_retryable(self) -> None:
        """ValueError (non-HTTP error) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(ValueError("oops")) is False

    def test_no_provider_types_connection_error(self) -> None:
        """Without provider types (artwork config), ConnectionError is retryable."""
        predicate = make_retryable_predicate()
        assert predicate(requests.exceptions.ConnectionError()) is True

    def test_no_provider_types_value_error(self) -> None:
        """Without provider types, ValueError is NOT retryable."""
        predicate = make_retryable_predicate()
        assert predicate(ValueError("oops")) is False

    def test_http_error_500_is_retryable(self) -> None:
        """requests.HTTPError with 500 response should be retryable."""
        predicate = make_retryable_predicate()
        response = requests.models.Response()
        response.status_code = 500
        exc = requests.exceptions.HTTPError(response=response)
        assert predicate(exc) is True

    def test_http_error_404_not_retryable(self) -> None:
        """requests.HTTPError with 404 response should NOT be retryable."""
        predicate = make_retryable_predicate()
        response = requests.models.Response()
        response.status_code = 404
        exc = requests.exceptions.HTTPError(response=response)
        assert predicate(exc) is False

    def test_multiple_provider_types(self) -> None:
        """Factory should accept multiple provider error types."""

        class _AnotherError(Exception):
            def __init__(self, http_status: int) -> None:
                self.http_status = http_status

        predicate = make_retryable_predicate(_FakeProviderError, _AnotherError)
        assert predicate(_FakeProviderError(503)) is True
        assert predicate(_AnotherError(504)) is True
        assert predicate(_AnotherError(403)) is False


# ---------------------------------------------------------------------------
# Retry-After parsing + wait strategy
# ---------------------------------------------------------------------------


from datetime import datetime, timedelta, timezone  # noqa: E402
from email.utils import format_datetime  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from tenacity import wait_fixed  # noqa: E402

from personalscraper.scraper.http_retry import (  # noqa: E402
    _parse_retry_after,
    wait_with_retry_after,
)


class TestParseRetryAfter:
    """Cover both forms permitted by RFC 7231 (delay-seconds and HTTP-date)."""

    def test_none_returns_none(self) -> None:
        """Missing header → None."""
        assert _parse_retry_after(None) is None

    def test_empty_returns_none(self) -> None:
        """Empty / whitespace-only header → None."""
        assert _parse_retry_after("") is None
        assert _parse_retry_after("   ") is None

    def test_integer_seconds(self) -> None:
        """Numeric form returns the integer as float seconds."""
        assert _parse_retry_after("42") == 42.0

    def test_negative_clamped_to_zero(self) -> None:
        """Negative seconds clamp to 0 (server bug, not our problem)."""
        assert _parse_retry_after("-5") == 0.0

    def test_http_date_future(self) -> None:
        """HTTP-date in the future returns the delta in seconds."""
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=120)
        value = _parse_retry_after(format_datetime(future, usegmt=True))
        assert value is not None
        assert 100 <= value <= 130  # generous tolerance for clock skew during the test

    def test_http_date_past_clamps_to_zero(self) -> None:
        """HTTP-date in the past → 0 (don't sleep into negatives)."""
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
        assert _parse_retry_after(format_datetime(past, usegmt=True)) == 0.0

    def test_garbage_returns_none(self) -> None:
        """Unparseable strings → None (fall through to default backoff)."""
        assert _parse_retry_after("not-a-date") is None


class TestWaitWithRetryAfter:
    """Verify the tenacity wait wrapper consumes Retry-After or falls back."""

    def _make_state(self, exc: BaseException | None) -> MagicMock:
        """Build a minimal RetryCallState mock carrying ``exc``."""
        outcome = MagicMock()
        outcome.exception.return_value = exc
        state = MagicMock()
        state.outcome = outcome
        return state

    def test_honors_retry_after_seconds(self) -> None:
        """A 429 with Retry-After: 30 → wait 30s, ignoring fallback."""
        response = requests.models.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "30"
        exc = requests.exceptions.HTTPError(response=response)
        wait = wait_with_retry_after(wait_fixed(1))
        assert wait(self._make_state(exc)) == 30.0

    def test_clamps_to_max_wait(self) -> None:
        """A pathological Retry-After: 99999 is clamped to ``max_wait``."""
        response = requests.models.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "99999"
        exc = requests.exceptions.HTTPError(response=response)
        wait = wait_with_retry_after(wait_fixed(1), max_wait=60.0)
        assert wait(self._make_state(exc)) == 60.0

    def test_falls_back_when_no_header(self) -> None:
        """No Retry-After → fallback strategy used."""
        response = requests.models.Response()
        response.status_code = 500  # 500 has no Retry-After typically
        exc = requests.exceptions.HTTPError(response=response)
        wait = wait_with_retry_after(wait_fixed(7))
        assert wait(self._make_state(exc)) == 7.0

    def test_provider_error_with_headers_attr(self) -> None:
        """Provider exceptions can surface headers directly via ``.headers``."""

        class _ProviderErrorWithHeaders(Exception):
            headers = {"Retry-After": "12"}

        wait = wait_with_retry_after(wait_fixed(1))
        assert wait(self._make_state(_ProviderErrorWithHeaders())) == 12.0
