"""Integration tests for HttpTransport network-error retry behavior.

Coverage gaps closed:
- HttpTransport retries ConnectionError / Timeout (`_http.py:209-212`).
  Previously only the 503 retry case was exercised in
  ``test_transport_policy.py``; transient network failures were uncovered.
- HttpTransport ApiError body extraction (`_http.py:170-180`):
  the three branches (``status_code``, ``code``, fallback to ``resp.reason``)
  plus the unparsable-HTML body path.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import requests
import responses

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._auth import NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import CircuitPolicy, RetryPolicy, TransportPolicy
from personalscraper.core.event_bus import EventBus

BASE = "http://transport-test.example.com"


def _make_policy(**overrides: Any) -> TransportPolicy:
    """Build a tight-retry policy suitable for fast tests."""
    kwargs: dict[str, Any] = {
        "provider_name": "TestAPI",
        "base_url": BASE,
        "auth": NoAuth(),
        "retry": RetryPolicy(max_attempts=3, initial_wait=0.001, max_wait=0.01),
        "circuit": CircuitPolicy(failure_threshold=10, cooldown_seconds=0.1, count_retries=False),
    }
    kwargs.update(overrides)
    return TransportPolicy(**kwargs)


# -- Retry on network failures -------------------------------------------------


class TestRetryOnConnectionError:
    """Coverage for `_is_retryable` ConnectionError / Timeout branch."""

    @responses.activate
    def test_retries_connection_error_then_succeeds(self) -> None:
        """A transient ConnectionError must be retried, then the call succeeds."""
        url = f"{BASE}/flaky"
        responses.add(responses.GET, url, body=requests.ConnectionError("connection reset"))
        responses.add(responses.GET, url, json={"ok": True}, status=200)

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            result = transport.get("/flaky")
        finally:
            transport.close()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(responses.calls) == 2, "Transport must retry ConnectionError once before succeeding."

    @responses.activate
    def test_retries_timeout_then_succeeds(self) -> None:
        """A transient Timeout must be retried, then the call succeeds."""
        url = f"{BASE}/slow"
        responses.add(responses.GET, url, body=requests.Timeout("read timed out"))
        responses.add(responses.GET, url, json={"ok": True}, status=200)

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            result = transport.get("/slow")
        finally:
            transport.close()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_connection_error_exhausts_retries_and_propagates(self) -> None:
        """When every attempt raises ConnectionError, the original exception escapes."""
        url = f"{BASE}/dead"
        for _ in range(3):
            responses.add(responses.GET, url, body=requests.ConnectionError("dead"))

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            with pytest.raises(requests.ConnectionError):
                transport.get("/dead")
        finally:
            transport.close()

        assert len(responses.calls) == 3, "All three attempts must have been made."


# -- Error-body extraction -----------------------------------------------------


class TestErrorBodyExtraction:
    """Coverage for ApiError extraction paths in `_http.py:170-180`."""

    @responses.activate
    def test_status_code_and_status_message_branch(self) -> None:
        """Body shape ``{status_code, status_message}`` (TMDB style) populates ApiError."""
        responses.add(
            responses.GET,
            re.compile(rf"{BASE}/missing"),
            json={"status_code": 34, "status_message": "Resource not found."},
            status=404,
        )

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            with pytest.raises(ApiError) as exc:
                transport.get("/missing")
        finally:
            transport.close()

        assert exc.value.http_status == 404
        assert exc.value.provider_code == 34
        assert "Resource not found." in exc.value.message

    @responses.activate
    def test_code_and_message_branch(self) -> None:
        """Body shape ``{code, message}`` (alternate provider style) populates ApiError."""
        responses.add(
            responses.GET,
            re.compile(rf"{BASE}/forbidden"),
            json={"code": 7, "message": "Access denied"},
            status=403,
        )

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            with pytest.raises(ApiError) as exc:
                transport.get("/forbidden")
        finally:
            transport.close()

        assert exc.value.http_status == 403
        assert exc.value.provider_code == 7
        assert exc.value.message == "Access denied"

    @responses.activate
    def test_unparsable_body_falls_back_to_reason(self) -> None:
        """An HTML body must not break ApiError construction; message falls back to resp.reason."""
        responses.add(
            responses.GET,
            re.compile(rf"{BASE}/proxy_html"),
            body="<html><body>502 Bad Gateway</body></html>",
            status=502,
            content_type="text/html",
        )

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        try:
            with pytest.raises(ApiError) as exc:
                transport.get("/proxy_html")
        finally:
            transport.close()

        assert exc.value.http_status == 502
        assert exc.value.provider_code == 0, "No provider_code present in HTML body."
        # message must be a non-empty string (resp.reason fallback)
        assert exc.value.message, "ApiError.message must fall back to resp.reason when body is unparsable."
