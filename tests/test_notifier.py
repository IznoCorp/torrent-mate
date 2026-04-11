"""Tests for personalscraper.notifier — Telegram client and healthcheck."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.config import Settings
from personalscraper.models import PipelineReport, StepReport
from personalscraper.notifier import TelegramNotifier, ping_healthcheck


@pytest.fixture()
def notifier():
    """Return a TelegramNotifier with fake credentials."""
    return TelegramNotifier(bot_token="fake-token", chat_id="12345")


@pytest.fixture()
def sample_report():
    """Return a PipelineReport with two steps."""
    report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
    report.add_step("ingest", StepReport(name="ingest", success_count=3, skip_count=1))
    report.add_step("sort", StepReport(name="sort", success_count=5, error_count=1))
    report.finished_at = datetime(2026, 4, 11, 3, 4, 32)
    return report


# ── TelegramNotifier.send ────────────────────────────


class TestSend:
    """Tests for TelegramNotifier.send()."""

    @patch("personalscraper.notifier.requests.post")
    def test_send_success(self, mock_post, notifier):
        """Successful API call returns True."""
        mock_post.return_value = MagicMock(ok=True)
        assert notifier.send("hello") is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["text"] == "hello"
        assert call_kwargs.kwargs["json"]["parse_mode"] == "HTML"

    @patch("personalscraper.notifier.requests.post")
    def test_send_api_error(self, mock_post, notifier):
        """Non-2xx response returns False without raising."""
        mock_post.return_value = MagicMock(ok=False, status_code=401, text="Unauthorized")
        assert notifier.send("hello") is False

    @patch("personalscraper.notifier.requests.post")
    def test_send_timeout(self, mock_post, notifier):
        """Timeout returns False without raising."""
        import requests
        mock_post.side_effect = requests.Timeout("timed out")
        assert notifier.send("hello") is False

    @patch("personalscraper.notifier.requests.post")
    def test_send_connection_error(self, mock_post, notifier):
        """Connection error returns False without raising."""
        mock_post.side_effect = ConnectionError("no route")
        assert notifier.send("hello") is False

    @patch("personalscraper.notifier.requests.post")
    def test_send_custom_parse_mode(self, mock_post, notifier):
        """Custom parse_mode is forwarded to the API."""
        mock_post.return_value = MagicMock(ok=True)
        notifier.send("hello", parse_mode="Markdown")
        assert mock_post.call_args.kwargs["json"]["parse_mode"] == "Markdown"


# ── TelegramNotifier.send_report ─────────────────────


class TestSendReport:
    """Tests for TelegramNotifier.send_report()."""

    @patch("personalscraper.notifier.requests.post")
    def test_send_report_calls_to_html(self, mock_post, notifier, sample_report):
        """send_report formats the report as HTML and sends it."""
        mock_post.return_value = MagicMock(ok=True)
        result = notifier.send_report(sample_report)
        assert result is True
        sent_text = mock_post.call_args.kwargs["json"]["text"]
        assert "<b>PersonalScraper" in sent_text


# ── TelegramNotifier.is_configured ───────────────────


class TestIsConfigured:
    """Tests for TelegramNotifier.is_configured()."""

    def test_configured_when_both_set(self):
        """Returns True when both token and chat_id are non-empty."""
        settings = Settings(telegram_bot_token="tok", telegram_chat_id="123")
        assert TelegramNotifier.is_configured(settings) is True

    def test_not_configured_missing_token(self):
        """Returns False when bot_token is empty."""
        settings = Settings(telegram_bot_token="", telegram_chat_id="123")
        assert TelegramNotifier.is_configured(settings) is False

    def test_not_configured_missing_chat_id(self):
        """Returns False when chat_id is empty."""
        settings = Settings(telegram_bot_token="tok", telegram_chat_id="")
        assert TelegramNotifier.is_configured(settings) is False

    def test_not_configured_both_empty(self):
        """Returns False when both are empty (default state)."""
        settings = Settings()
        assert TelegramNotifier.is_configured(settings) is False


# ── ping_healthcheck ─────────────────────────────────


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
