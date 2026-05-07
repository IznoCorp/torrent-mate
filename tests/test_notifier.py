"""Tests for personalscraper.notifier — healthcheck pinger only.

The Telegram notifier moved to ``personalscraper.api.notify.telegram`` in
Phase 22 of the api-unify feature; its tests live in
``tests/unit/test_telegram_notifier.py``. This module now only covers the
healthcheck helper, which stays in ``personalscraper/notifier.py`` until
Phase 24.
"""

from unittest.mock import patch

from personalscraper.notifier import ping_healthcheck


class TestPingHealthcheck:
    """Tests for the ping_healthcheck function."""

    @patch("personalscraper.notifier.requests.get")
    def test_ping_success(self, mock_get):
        """Pings the correct URL with status suffix."""
        ping_healthcheck("https://hc-ping.com/abc", "/start")
        mock_get.assert_called_once_with("https://hc-ping.com/abc/start", timeout=5)

    @patch("personalscraper.notifier.requests.get")
    def test_ping_empty_url_noop(self, mock_get):
        """Empty URL does nothing (silent skip)."""
        ping_healthcheck("", "/start")
        mock_get.assert_not_called()

    @patch("personalscraper.notifier.requests.get")
    def test_ping_exception_swallowed(self, mock_get):
        """Exceptions are swallowed — never raises."""
        mock_get.side_effect = ConnectionError("down")
        ping_healthcheck("https://hc-ping.com/abc")  # Should not raise

    @patch("personalscraper.notifier.requests.get")
    def test_ping_default_status_is_success(self, mock_get):
        """Default status is empty string (success endpoint)."""
        ping_healthcheck("https://hc-ping.com/abc")
        mock_get.assert_called_once_with("https://hc-ping.com/abc", timeout=5)
