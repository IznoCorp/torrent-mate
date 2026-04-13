"""Tests for personalscraper.scraper.http_retry — shared retry predicates."""

import requests
import requests.exceptions
import requests.models

from personalscraper.scraper.http_retry import make_retryable_predicate


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
