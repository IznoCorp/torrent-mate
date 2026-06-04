"""Reference integration test for HttpTransport consuming TransportPolicy."""

from __future__ import annotations

import re
from typing import Any

import pytest
import responses

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.transport._auth import ApiKeyAuth, NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import CircuitPolicy, RetryPolicy, TransportPolicy
from personalscraper.core.event_bus import EventBus

BASE = "http://test-api.example.com"


def _make_policy(**overrides: Any) -> TransportPolicy:
    kwargs: dict[str, Any] = {
        "provider_name": "TestAPI",
        "base_url": BASE,
        "auth": ApiKeyAuth("test-key", location="query"),
        "retry": RetryPolicy(max_attempts=3, initial_wait=0.001, max_wait=0.01),
        "circuit": CircuitPolicy(failure_threshold=2, cooldown_seconds=0.1, count_retries=False),
    }
    kwargs.update(overrides)
    return TransportPolicy(**kwargs)


class TestQueryAuthParam:
    """Auth query param is sent on every request."""

    @responses.activate
    def test_query_auth_sent(self) -> None:
        """ApiKeyAuth(location='query') adds api_key to query params."""
        responses.add(responses.GET, re.compile(rf"{BASE}/test"), json={"ok": True})

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        transport.get("/test")
        transport.close()

        req = responses.calls[0].request
        assert req.url is not None
        assert "api_key=test-key" in req.url


class TestRetryBehavior:
    """Retry on 503, success on 3rd call."""

    @responses.activate
    def test_retries_on_503(self) -> None:
        """Retries 503 twice, succeeds on third attempt."""
        url = f"{BASE}/flaky"
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"ok": True}, status=200)

        transport = HttpTransport(_make_policy(), event_bus=EventBus())
        result = transport.get("/flaky")
        transport.close()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(responses.calls) == 3


class TestCircuitBreaker:
    """Circuit opens after 2 final failures (not 2 attempts inside one call)."""

    @responses.activate
    def test_circuit_opens_after_two_failures(self) -> None:
        """Circuit opens after 2 final failures (count_retries=False)."""
        url = f"{BASE}/down"

        # Call 1: fails after 3 attempts (max_attempts=3), 1 final failure
        for _ in range(3):
            responses.add(responses.GET, url, json={"error": "down"}, status=500)
        # Call 2: fails after 3 attempts, 2nd final failure -> circuit opens
        for _ in range(3):
            responses.add(responses.GET, url, json={"error": "down"}, status=500)

        transport = HttpTransport(_make_policy(), event_bus=EventBus())

        # Call 1 — fails, circuit records 1 final failure
        with pytest.raises(ApiError):
            transport.get("/down")
        # Call 2 — fails, circuit records 2nd final failure -> opens
        with pytest.raises(ApiError):
            transport.get("/down")
        # Call 3 — circuit is open
        with pytest.raises(CircuitOpenError, match="Circuit breaker OPEN"):
            transport.get("/down")

        transport.close()

    def test_circuit_breaker_ignores_internal_typeerror(self) -> None:
        """TypeError (internal bug) propagates WITHOUT tripping the circuit breaker."""
        transport = HttpTransport(_make_policy(), event_bus=EventBus())

        def _raise_typeerror(*_args: Any, **_kwargs: Any) -> Any:
            raise TypeError("internal bug")

        transport._do_request_raw = _raise_typeerror  # type: ignore[method-assign]
        failure_before = transport._circuit._failure_count

        with pytest.raises(TypeError, match="internal bug"):
            transport.get("/bug")

        assert transport._circuit._failure_count == failure_before
        transport.close()


class TestResponseFormats:
    """response_format controls body parsing."""

    @responses.activate
    def test_text_format(self) -> None:
        """'text' response_format returns resp.text unchanged."""
        url = f"{BASE}/text"
        responses.add(responses.GET, url, body="plain text response", status=200)

        transport = HttpTransport(_make_policy(response_format="text", auth=NoAuth()), event_bus=EventBus())
        result = transport.get("/text")
        transport.close()

        assert result == "plain text response"

    @responses.activate
    def test_xml_format(self) -> None:
        """'xml' response_format parses XML into a dict."""
        url = f"{BASE}/xml"
        responses.add(
            responses.GET,
            url,
            body="<root><item>value</item></root>",
            status=200,
            content_type="application/xml",
        )

        transport = HttpTransport(_make_policy(response_format="xml", auth=NoAuth()), event_bus=EventBus())
        result = transport.get("/xml")
        transport.close()

        assert result == {"root": {"item": "value"}}


class TestPolicyImmutability:
    """``TransportPolicy`` is frozen — accidental mutation must raise."""

    def test_policy_is_frozen(self) -> None:
        """Reassigning a ``TransportPolicy`` field must raise ``FrozenInstanceError``."""
        from dataclasses import FrozenInstanceError

        policy = _make_policy()
        with pytest.raises(FrozenInstanceError):
            policy.timeout_seconds = 99.0  # type: ignore[misc]
