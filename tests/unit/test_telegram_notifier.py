"""Tests for Telegram notifier — api/notify/telegram.py."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.api.transport._auth import NoAuth
from personalscraper.config import Settings
from personalscraper.models import PipelineReport, StepReport


def _make_notifier(transport: MagicMock | None = None) -> TelegramNotifier:
    """Build a TelegramNotifier with a mock transport for unit tests."""
    return TelegramNotifier(transport or MagicMock(), chat_id="12345")


def _sample_report() -> PipelineReport:
    """Return a small PipelineReport for send_report() tests."""
    report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
    report.add_step("ingest", StepReport(name="ingest", success_count=3, skip_count=1))
    report.add_step("sort", StepReport(name="sort", success_count=5, error_count=1))
    report.finished_at = datetime(2026, 4, 11, 3, 4, 32)
    return report


# -- TransportPolicy ----------------------------------------------------------


class TestPolicy:
    """TelegramNotifier.policy() — TransportPolicy construction."""

    def test_token_embedded_in_base_url(self) -> None:
        """Bot token is part of the URL path; auth is NoAuth (token-in-URL)."""
        policy = TelegramNotifier.policy("8266923011:AAEXAMPLE")
        assert policy.base_url == "https://api.telegram.org/bot8266923011:AAEXAMPLE"
        assert isinstance(policy.auth, NoAuth)

    def test_provider_name_is_telegram(self) -> None:
        """provider_name is "telegram" — used by structured logging."""
        assert TelegramNotifier.policy("t").provider_name == "telegram"

    def test_rate_limit_one_per_second(self) -> None:
        """Per-chat ceiling: 1 msg/sec (Telegram FAQ)."""
        policy = TelegramNotifier.policy("t")
        assert policy.rate_limit.requests_per_second == 1.0

    def test_circuit_is_tolerant(self) -> None:
        """Notification is best-effort — failure_threshold ≥ 10, short cooldown."""
        policy = TelegramNotifier.policy("t")
        assert policy.circuit.failure_threshold >= 10
        assert policy.circuit.cooldown_seconds <= 120.0


# -- send() — happy path ------------------------------------------------------


class TestSendSuccess:
    """TelegramNotifier.send() — success cases."""

    def test_send_posts_to_sendmessage_path(self) -> None:
        """send() POSTs to /sendMessage with chat_id, text, parse_mode."""
        notifier = _make_notifier()
        assert notifier.send("hello") is True

        notifier._transport.post.assert_called_once()
        call_args = notifier._transport.post.call_args
        assert call_args.args[0] == "/sendMessage"
        body = call_args.kwargs["data"]
        assert body == {"chat_id": "12345", "text": "hello", "parse_mode": "HTML"}

    def test_send_custom_parse_mode_forwarded(self) -> None:
        """parse_mode kwarg is forwarded verbatim to the API."""
        notifier = _make_notifier()
        notifier.send("hello", parse_mode="MarkdownV2")
        body = notifier._transport.post.call_args.kwargs["data"]
        assert body["parse_mode"] == "MarkdownV2"


# -- send() — fail-soft -------------------------------------------------------


class TestSendFailSoft:
    """TelegramNotifier.send() — fail-soft contract (never raises)."""

    def test_apierror_returns_false(self) -> None:
        """ApiError raised by transport → send() returns False, no re-raise."""
        notifier = _make_notifier()
        notifier._transport.post.side_effect = ApiError(
            provider="telegram",
            http_status=400,
            message="Bad Request: chat not found",
        )
        assert notifier.send("hello") is False

    def test_unexpected_exception_returns_false(self) -> None:
        """Unexpected exceptions are caught — pipeline never aborts on notification."""
        notifier = _make_notifier()
        notifier._transport.post.side_effect = RuntimeError("boom")
        assert notifier.send("hello") is False

    def test_401_unauthorized_returns_false(self) -> None:
        """Bad token (401) → fail-soft False, logs warning."""
        notifier = _make_notifier()
        notifier._transport.post.side_effect = ApiError(
            provider="telegram",
            http_status=401,
            message="Unauthorized: invalid token specified",
        )
        assert notifier.send("hello") is False


# -- Long-message chunking ----------------------------------------------------


class TestChunking:
    """TelegramNotifier._chunk() and chunked send() behavior."""

    def test_chunk_short_text_single_piece(self) -> None:
        """Text under cap → single chunk."""
        chunks = TelegramNotifier._chunk("hello", max_len=4096)
        assert chunks == ["hello"]

    def test_chunk_at_boundary(self) -> None:
        """Text exactly at cap → single chunk of cap size."""
        text = "a" * 4096
        assert TelegramNotifier._chunk(text, max_len=4096) == [text]

    def test_chunk_over_cap_splits_evenly(self) -> None:
        """Text > cap → split into max_len pieces."""
        text = "a" * 4500
        chunks = TelegramNotifier._chunk(text, max_len=4096)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 4096
        assert chunks[1] == "a" * 404

    def test_chunk_empty_text_returns_one_empty(self) -> None:
        """Empty input still yields one chunk so the API surfaces its own 400."""
        assert TelegramNotifier._chunk("", max_len=4096) == [""]

    def test_send_long_message_issues_multiple_posts(self) -> None:
        """Send of 4500-char message → 2 POSTs to /sendMessage."""
        notifier = _make_notifier()
        big = "x" * 4500
        assert notifier.send(big) is True
        assert notifier._transport.post.call_count == 2

        first_body = notifier._transport.post.call_args_list[0].kwargs["data"]
        second_body = notifier._transport.post.call_args_list[1].kwargs["data"]
        assert first_body["text"] == "x" * 4096
        assert second_body["text"] == "x" * 404

    def test_send_long_message_first_chunk_fails_aborts(self) -> None:
        """Mid-send error → remaining chunks are NOT sent (fail-soft)."""
        notifier = _make_notifier()
        notifier._transport.post.side_effect = [
            None,
            ApiError(provider="telegram", http_status=400, message="bad"),
        ]
        big = "x" * 4500
        assert notifier.send(big) is False
        assert notifier._transport.post.call_count == 2


# -- send_report() ------------------------------------------------------------


class TestSendReport:
    """TelegramNotifier.send_report() — serializes via PipelineReport.to_html()."""

    def test_send_report_calls_to_html_and_posts(self) -> None:
        """send_report() forwards report.to_html() through send()."""
        notifier = _make_notifier()
        result = notifier.send_report(_sample_report())
        assert result is True
        body = notifier._transport.post.call_args.kwargs["data"]
        assert "<b>" in body["text"]


# -- is_configured() ----------------------------------------------------------


class TestIsConfigured:
    """TelegramNotifier.is_configured() — credential presence check."""

    def test_both_set_returns_true(self) -> None:
        """Both creds present → True."""
        settings = Settings(telegram_bot_token="tok", telegram_chat_id="123")
        assert TelegramNotifier.is_configured(settings) is True

    def test_missing_token_returns_false(self) -> None:
        """Empty bot_token → False."""
        settings = Settings(telegram_bot_token="", telegram_chat_id="123")
        assert TelegramNotifier.is_configured(settings) is False

    def test_missing_chat_id_returns_false(self) -> None:
        """Empty chat_id → False."""
        settings = Settings(telegram_bot_token="tok", telegram_chat_id="")
        assert TelegramNotifier.is_configured(settings) is False

    def test_both_empty_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default-empty Settings (env stripped) → False."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        settings = Settings(_env_file=None)
        assert TelegramNotifier.is_configured(settings) is False
