"""Tests for Healthcheck client — api/notify/healthchecks.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.notify.healthchecks import HealthcheckClient
from personalscraper.api.transport._auth import NoAuth
from personalscraper.config import Settings


def _make_client(transport: MagicMock | None = None) -> HealthcheckClient:
    """Build a HealthcheckClient with a mock transport for unit tests."""
    return HealthcheckClient(transport or MagicMock())


# -- TransportPolicy ----------------------------------------------------------


class TestPolicy:
    """HealthcheckClient.policy() — TransportPolicy construction."""

    def test_url_used_as_base(self) -> None:
        """ping_url passed as base_url verbatim (self-hosted-friendly)."""
        policy = HealthcheckClient.policy("https://hc-ping.com/abc-123")
        assert policy.base_url == "https://hc-ping.com/abc-123"

    def test_no_auth(self) -> None:
        """UUID-in-URL → NoAuth (no header, no query param)."""
        policy = HealthcheckClient.policy("https://hc-ping.com/abc")
        assert isinstance(policy.auth, NoAuth)

    def test_response_format_text(self) -> None:
        """Healthchecks returns plain-text — must use response_format='text'."""
        policy = HealthcheckClient.policy("https://hc-ping.com/abc")
        assert policy.response_format == "text"

    def test_provider_name(self) -> None:
        """provider_name is "healthchecks"."""
        assert HealthcheckClient.policy("x").provider_name == "healthchecks"


# -- ping_* lifecycle ---------------------------------------------------------


class TestPingLifecycle:
    """HealthcheckClient.ping_start/success/fail() — URL routing."""

    def test_ping_start_appends_start_suffix(self) -> None:
        """ping_start() → GET '/start' relative to base_url."""
        client = _make_client()
        client.ping_start()
        client._transport.get.assert_called_once_with("/start")

    def test_ping_success_uses_empty_path(self) -> None:
        """ping_success() → GET '' (the base URL itself)."""
        client = _make_client()
        client.ping_success()
        client._transport.get.assert_called_once_with("")

    def test_ping_fail_appends_fail_suffix(self) -> None:
        """ping_fail() → GET '/fail'."""
        client = _make_client()
        client.ping_fail()
        client._transport.get.assert_called_once_with("/fail")

    def test_methods_return_none(self) -> None:
        """Protocol returns None — pure side-effect."""
        client = _make_client()
        assert client.ping_start() is None
        assert client.ping_success() is None
        assert client.ping_fail() is None


# -- Fail-soft contract -------------------------------------------------------


class TestFailSoft:
    """HealthcheckClient — never raises, no matter what the transport does."""

    def test_apierror_swallowed(self) -> None:
        """ApiError from transport → ping_* returns silently."""
        client = _make_client()
        client._transport.get.side_effect = ApiError(
            provider="healthchecks",
            http_status=404,
            message="(not found)",
        )
        client.ping_start()  # MUST NOT raise

    def test_connection_error_swallowed(self) -> None:
        """ConnectionError → ping_* returns silently."""
        client = _make_client()
        client._transport.get.side_effect = ConnectionError("no route")
        client.ping_success()  # MUST NOT raise

    def test_timeout_swallowed(self) -> None:
        """TimeoutError → ping_* returns silently."""
        client = _make_client()
        client._transport.get.side_effect = TimeoutError("slow")
        client.ping_fail()  # MUST NOT raise

    def test_unexpected_exception_swallowed(self) -> None:
        """Even RuntimeError is caught — pipeline never aborts on a ping."""
        client = _make_client()
        client._transport.get.side_effect = RuntimeError("boom")
        client.ping_start()  # MUST NOT raise


# -- is_configured() ----------------------------------------------------------


class TestIsConfigured:
    """HealthcheckClient.is_configured() — credential presence check."""

    def test_url_set_returns_true(self) -> None:
        """healthcheck_url present → True."""
        settings = Settings(healthcheck_url="https://hc-ping.com/abc")
        assert HealthcheckClient.is_configured(settings) is True

    def test_empty_url_returns_false(self) -> None:
        """Empty healthcheck_url → False (default-empty Settings)."""
        settings = Settings(healthcheck_url="")
        assert HealthcheckClient.is_configured(settings) is False

    def test_default_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No env, no override → False (env stripped)."""
        monkeypatch.delenv("HEALTHCHECK_URL", raising=False)
        settings = Settings(_env_file=None)
        assert HealthcheckClient.is_configured(settings) is False
